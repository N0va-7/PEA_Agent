import json
import time
from datetime import datetime, timedelta
from typing import Any

import requests
import streamlit as st


st.set_page_config(
    page_title="邮件安全分析前端",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
:root {
  --bg-soft: #f3f6fb;
  --card: #ffffff;
  --line: #d9e2ef;
  --danger: #c62828;
  --warning: #f57c00;
  --safe: #2e7d32;
  --text: #0f172a;
}
[data-testid="stAppViewContainer"] {
  background: radial-gradient(1200px 600px at 10% -20%, #e8eefc, #f5f7fb 45%, #f3f6fb 100%);
}
.metric-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px 14px;
}
.status-chip {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  border: 1px solid var(--line);
  background: #fff;
}
</style>
""",
    unsafe_allow_html=True,
)


DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT = 30
POLL_INTERVAL_SECONDS = 1.0
MAX_POLL_SECONDS = 240


for key, value in {
    "backend_url": DEFAULT_BACKEND_URL,
    "access_token": "",
    "token_expire_at": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = value


class ApiError(RuntimeError):
    pass



def _normalize_base_url(url: str) -> str:
    return (url or "").strip().rstrip("/")



def _api_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}



def _safe_json(resp: requests.Response) -> dict[str, Any]:
    try:
        return resp.json()
    except Exception:
        return {"detail": resp.text}



def login(base_url: str, username: str, password: str) -> tuple[str, datetime | None]:
    try:
        resp = requests.post(
            f"{base_url}/api/v1/auth/login",
            json={"username": username, "password": password},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ApiError(f"登录请求失败: {exc}") from exc

    if resp.status_code != 200:
        detail = _safe_json(resp).get("detail", "未知错误")
        raise ApiError(f"登录失败 ({resp.status_code}): {detail}")

    payload = resp.json()
    token = payload.get("access_token", "")
    expires_in = int(payload.get("expires_in", 0))
    expire_at = datetime.now() + timedelta(seconds=expires_in) if expires_in > 0 else None
    return token, expire_at



def create_analysis_job(base_url: str, token: str, filename: str, file_bytes: bytes) -> str:
    files = {"file": (filename, file_bytes, "message/rfc822")}
    try:
        resp = requests.post(
            f"{base_url}/api/v1/analyses",
            files=files,
            headers=_api_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ApiError(f"创建任务失败: {exc}") from exc

    if resp.status_code != 200:
        detail = _safe_json(resp).get("detail", "未知错误")
        raise ApiError(f"创建任务失败 ({resp.status_code}): {detail}")

    payload = resp.json()
    return payload["job_id"]



def get_job(base_url: str, token: str, job_id: str) -> dict[str, Any]:
    try:
        resp = requests.get(
            f"{base_url}/api/v1/jobs/{job_id}",
            headers=_api_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ApiError(f"查询任务失败: {exc}") from exc

    if resp.status_code != 200:
        detail = _safe_json(resp).get("detail", "未知错误")
        raise ApiError(f"查询任务失败 ({resp.status_code}): {detail}")
    return resp.json()



def get_analysis(base_url: str, token: str, analysis_id: str) -> dict[str, Any]:
    try:
        resp = requests.get(
            f"{base_url}/api/v1/analyses/{analysis_id}",
            headers=_api_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ApiError(f"查询分析结果失败: {exc}") from exc

    if resp.status_code != 200:
        detail = _safe_json(resp).get("detail", "未知错误")
        raise ApiError(f"查询分析结果失败 ({resp.status_code}): {detail}")

    return resp.json()



def download_report(base_url: str, token: str, analysis_id: str) -> tuple[bytes, str]:
    try:
        resp = requests.get(
            f"{base_url}/api/v1/reports/{analysis_id}",
            headers=_api_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ApiError(f"下载报告失败: {exc}") from exc

    if resp.status_code != 200:
        detail = _safe_json(resp).get("detail", "未知错误")
        raise ApiError(f"下载报告失败 ({resp.status_code}): {detail}")

    filename = f"report_{analysis_id}.md"
    content_disposition = resp.headers.get("content-disposition", "")
    if "filename=" in content_disposition:
        filename = content_disposition.split("filename=")[-1].strip('"')
    return resp.content, filename



def poll_job_until_done(base_url: str, token: str, job_id: str, status_box, log_area) -> dict[str, Any]:
    logs: list[str] = [f"任务已创建: {job_id}"]
    start = time.time()

    while True:
        payload = get_job(base_url, token, job_id)
        status = payload.get("status", "unknown")
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 任务状态: {status}")
        log_area.code("\n".join(logs), language="text")
        status_box.update(label=f"任务执行中: {status}", state="running", expanded=True)

        if status in {"succeeded", "failed", "cached"}:
            return payload

        if time.time() - start > MAX_POLL_SECONDS:
            raise ApiError("任务轮询超时，请稍后在历史列表查询结果。")

        time.sleep(POLL_INTERVAL_SECONDS)



def render_result(analysis: dict[str, Any], job_status: dict[str, Any], report_bytes: bytes, report_name: str):
    final_decision = analysis.get("final_decision") or {}
    body_analysis = analysis.get("body_analysis") or {}
    url_analysis = analysis.get("url_analysis") or {}
    attachment_analysis = analysis.get("attachment_analysis") or {}

    malicious = bool(final_decision.get("is_malicious", False))
    score = float(final_decision.get("score", 0.0))
    body_prob = float(body_analysis.get("phishing_probability", 0.0))
    url_prob = float(url_analysis.get("max_possibility", 0.0))
    att_level = attachment_analysis.get("threat_level", "unknown")

    st.markdown("### 分析总览")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("最终判定", "恶意" if malicious else "正常", delta=f"score={score:.3f}")
    with col2:
        st.metric("正文钓鱼概率", f"{body_prob * 100:.2f}%")
    with col3:
        st.metric("URL钓鱼概率", f"{url_prob * 100:.2f}%")
    with col4:
        st.metric("附件威胁等级", str(att_level).upper())

    cache_hit = job_status.get("status") == "cached"
    chip = "命中历史缓存" if cache_hit else "新分析结果"
    st.markdown(f"<span class='status-chip'>{chip}</span>", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("最终报告")
    st.markdown(analysis.get("llm_report") or "无报告内容")

    st.download_button(
        label="下载 Markdown 报告",
        data=report_bytes,
        file_name=report_name,
        mime="text/markdown",
        use_container_width=True,
    )

    with st.expander("查看原始JSON结果"):
        st.code(json.dumps(analysis, ensure_ascii=False, indent=2), language="json")


st.title("邮件安全分析前端")
st.caption("前后端解耦模式: Streamlit 仅调用后端 REST API")

with st.sidebar:
    st.header("后端连接")
    backend_url = st.text_input("Backend URL", value=st.session_state["backend_url"], help="例如: http://127.0.0.1:8000")
    backend_url = _normalize_base_url(backend_url)
    st.session_state["backend_url"] = backend_url

    st.header("登录")
    username = st.text_input("用户名", value="admin")
    password = st.text_input("密码", type="password")
    login_btn = st.button("登录获取令牌", use_container_width=True)

    if login_btn:
        if not backend_url:
            st.error("请先填写 Backend URL")
        elif not username or not password:
            st.error("请输入用户名和密码")
        else:
            try:
                token, expire_at = login(backend_url, username, password)
                st.session_state["access_token"] = token
                st.session_state["token_expire_at"] = expire_at
                st.success("登录成功")
            except ApiError as exc:
                st.error(str(exc))

    token = st.session_state.get("access_token", "")
    token_expire_at = st.session_state.get("token_expire_at")
    if token:
        expire_text = token_expire_at.strftime("%Y-%m-%d %H:%M:%S") if token_expire_at else "未知"
        st.info(f"已登录，令牌过期时间: {expire_text}")
    else:
        st.warning("未登录")

    st.divider()
    st.header("样本上传")
    uploaded_file = st.file_uploader("上传 .eml 文件", type=["eml"])
    start_btn = st.button("开始分析", type="primary", use_container_width=True)


if start_btn:
    token = st.session_state.get("access_token", "")
    if not backend_url:
        st.error("请先配置 Backend URL")
    elif not token:
        st.error("请先登录")
    elif uploaded_file is None:
        st.warning("请先上传 .eml 文件")
    else:
        status_box = st.status("准备提交任务...", expanded=True)
        log_area = st.empty()
        try:
            file_bytes = uploaded_file.getvalue()
            job_id = create_analysis_job(backend_url, token, uploaded_file.name, file_bytes)
            status_box.update(label="任务已提交，开始轮询", state="running", expanded=True)

            job_payload = poll_job_until_done(backend_url, token, job_id, status_box, log_area)
            if job_payload.get("status") == "failed":
                status_box.update(label="任务执行失败", state="error", expanded=True)
                st.error(job_payload.get("error", "未知错误"))
            else:
                analysis_id = job_payload.get("analysis_id")
                analysis = get_analysis(backend_url, token, analysis_id)
                report_bytes, report_name = download_report(backend_url, token, analysis_id)
                status_box.update(label="分析完成", state="complete", expanded=False)
                render_result(analysis, job_payload, report_bytes, report_name)
        except ApiError as exc:
            status_box.update(label="请求失败", state="error", expanded=True)
            st.error(str(exc))
        except Exception as exc:
            status_box.update(label="前端处理失败", state="error", expanded=True)
            st.exception(exc)
