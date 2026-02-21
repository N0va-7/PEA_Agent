import json
import re

from langchain_core.messages import SystemMessage

from backend.workflow.state import EmailAnalysisState


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_list(value, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _ensure_zh_text(value: str, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    return text if _has_cjk(text) else fallback


def _ensure_zh_list(values: list[str], fallback: list[str], *, limit: int = 8) -> list[str]:
    filtered = []
    for item in values[:limit]:
        text = str(item or "").strip()
        if text and _has_cjk(text):
            filtered.append(text)
    return filtered or fallback


def _extract_json_payload(content: str) -> dict:
    raw = (content or "").strip()
    if not raw:
        return {}

    for pattern in [
        r"<json>\s*(\{.*?\})\s*</json>",
        r"```json\s*(\{.*?\})\s*```",
    ]:
        match = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                payload = json.loads(match.group(1).strip())
                return payload if isinstance(payload, dict) else {}
            except json.JSONDecodeError:
                pass

    first = raw.find("{")
    last = raw.rfind("}")
    if first >= 0 and last > first:
        try:
            payload = json.loads(raw[first : last + 1].strip())
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _request_structured_sections(llm, state: EmailAnalysisState) -> dict:
    prompt = f"""
你是企业邮件安全分析师。请严格输出 JSON，不要输出 Markdown、不要输出多余解释。
所有字段必须使用简体中文，不要夹杂英文句子。

字段要求：
1) summary: 120-220字，完整说明攻击意图、判定依据、潜在影响。
2) risk_level: 仅可输出“高”“中”“低”之一。
3) key_indicators: 4-8条，每条10-30字，说明证据与风险点。
4) recommendations: 4-8条，每条10-35字，必须可执行。

输入数据：
- 主题: {state.get('subject', '')}
- 发件人: {state.get('sender', '')}
- 收件人: {state.get('recipient', '')}
- URL分析: {state.get('url_analysis', {})}
- 正文分析: {state.get('body_analysis', {})}
- 附件分析: {state.get('attachment_analysis', {})}
- 最终判定: {state.get('final_decision', {})}
"""
    response = llm.invoke([SystemMessage(content=prompt)])
    payload = _extract_json_payload(str(getattr(response, "content", "") or ""))
    return payload if isinstance(payload, dict) else {}


def _normalize_risk_level(raw_value: str, *, malicious: bool | None, score: float) -> str:
    text = str(raw_value or "").strip().lower()
    mapping = {
        "high": "高",
        "medium": "中",
        "low": "低",
        "critical": "高",
        "高": "高",
        "中": "中",
        "低": "低",
    }
    if text in mapping:
        return mapping[text]
    if malicious is True:
        return "高" if score >= 0.85 else "中"
    if malicious is False:
        return "低" if score <= 0.30 else "中"
    if score >= 0.80:
        return "高"
    if score <= 0.30:
        return "低"
    return "中"


def _default_summary(
    *,
    verdict: str,
    score: float,
    body_prob: float,
    url_prob: float,
    reason: str,
    risk_level: str,
) -> str:
    base = (
        f"系统综合正文、URL与附件信号后，当前邮件风险等级评估为{risk_level}，判定结果为{verdict}。"
        f"综合评分为{score:.4f}，正文钓鱼概率为{body_prob:.4f}，URL钓鱼概率为{url_prob:.4f}。"
    )
    if reason:
        base += f"核心判定理由为：{reason}。"
    if verdict == "恶意":
        base += "该邮件具备明显诱导或仿冒特征，存在凭据窃取、恶意跳转或后续入侵风险，建议按高优先级事件处置。"
    elif verdict == "正常":
        base += "当前未发现强恶意信号，但仍建议结合业务上下文持续观察同发件人及同主题样本变化。"
    else:
        base += "由于关键信息不足或信号不一致，建议进行人工复核后再执行最终处置。"
    return base


def _default_indicators(*, body_prob: float, url_prob: float, attachment_level: str, reason: str) -> list[str]:
    indicators = [
        f"正文模型给出钓鱼概率 {body_prob:.4f}，需关注社工诱导内容。",
        f"URL模型给出最高风险概率 {url_prob:.4f}，需核验链接指向与域名信誉。",
        f"附件威胁等级判定为 {attachment_level}，建议确认是否存在可执行载荷。",
    ]
    if reason:
        indicators.append(f"综合决策节点给出的判定依据：{reason}。")
    return indicators


def _default_recommendations(verdict: str) -> list[str]:
    if verdict == "恶意":
        return [
            "立即隔离该邮件并暂停相关账号的高风险操作权限。",
            "封禁可疑域名、URL与发件地址，并同步至邮件网关策略。",
            "通知受影响用户进行密码重置与多因素认证复核。",
            "提取IOC并在终端与网络侧进行横向排查与告警追溯。",
            "形成事件工单并在24小时内完成复盘与规则加固。",
        ]
    if verdict == "正常":
        return [
            "将该样本归档为低风险案例并保留原始证据链。",
            "持续监控同发件域、同主题模板在近7天内的异常波动。",
            "对关键收件人开启相似邮件命中提醒，降低漏报概率。",
            "定期复核模型阈值，确保业务低风险邮件不被误判。",
        ]
    return [
        "将样本转交人工复核，重点核验业务上下文与账号行为。",
        "在结论未确认前，建议对相关链接与附件执行临时隔离策略。",
        "补充邮件头与历史通信关系数据后重新运行分析流程。",
        "将该样本纳入反馈集，供后续阈值与权重优化使用。",
    ]


def _build_fixed_markdown(state: EmailAnalysisState, enrich: dict) -> str:
    final = state.get("final_decision", {}) or {}
    attach = state.get("attachment_analysis", {}) or {}
    body = state.get("body_analysis", {}) or {}
    url = state.get("url_analysis", {}) or {}

    malicious = final.get("is_malicious")
    verdict = "恶意" if malicious is True else ("正常" if malicious is False else "未判定")
    score = _as_float(final.get("score"), 0.0)
    body_prob = _as_float(body.get("phishing_probability"), 0.0)
    url_prob = _as_float(url.get("max_possibility"), 0.0)
    reason = str(final.get("reason") or "").strip()
    risk_level = _normalize_risk_level(str(enrich.get("risk_level") or ""), malicious=malicious, score=score)
    summary = _ensure_zh_text(
        str(enrich.get("summary") or "").strip(),
        _default_summary(
            verdict=verdict,
            score=score,
            body_prob=body_prob,
            url_prob=url_prob,
            reason=reason,
            risk_level=risk_level,
        ),
    )

    key_indicators = _ensure_zh_list(
        _safe_list(enrich.get("key_indicators")),
        _default_indicators(
            body_prob=body_prob,
            url_prob=url_prob,
            attachment_level=str(attach.get("threat_level", "unknown")),
            reason=reason,
        ),
    )

    recommendations = _ensure_zh_list(
        _safe_list(enrich.get("recommendations")),
        _default_recommendations(verdict),
    )

    url_items = [k for k in url.keys() if k != "max_possibility"]
    url_preview = "；".join(url_items[:5]) if url_items else "未提取到可供展示的URL样本"
    impact_text = (
        "该邮件可能导致账号凭据泄露、资金操作被劫持或内部横向传播，建议按安全事件流程执行阻断与排查。"
        if verdict == "恶意"
        else "当前未见直接攻击证据，但仍可能存在业务伪装或低强度社工尝试，建议结合人工复核结果持续监控。"
    )
    review_text = (
        "建议由安全运营人员结合邮件头、通信历史和业务场景进行二次复核，并将结论反馈至样本库。"
    )

    model_snapshot = {
        "body_phishing_probability": round(body_prob, 6),
        "url_max_probability": round(url_prob, 6),
        "attachment_threat_level": attach.get("threat_level", "unknown"),
        "final_score": round(score, 6),
        "config_source": final.get("config_source"),
    }
    snapshot_text = json.dumps(model_snapshot, ensure_ascii=False, indent=2)

    indicators_md = "\n".join(f"- {item}" for item in key_indicators)
    rec_md = "\n".join(f"{idx}. {item}" for idx, item in enumerate(recommendations, start=1))

    return (
        "# 邮件威胁分析报告\n\n"
        "## 1. 执行摘要\n"
        f"{summary}\n\n"
        "## 2. 邮件基础信息\n"
        f"- 主题: {state.get('subject') or '--'}\n"
        f"- 发件人: {state.get('sender') or '--'}\n"
        f"- 收件人: {state.get('recipient') or '--'}\n\n"
        "## 3. 检测结果总览\n"
        "| 指标 | 值 |\n"
        "| --- | --- |\n"
        f"| 判定结果 | {verdict} |\n"
        f"| 风险等级 | {risk_level} |\n"
        f"| 综合评分 | {score:.4f} |\n"
        f"| 正文钓鱼概率 | {body_prob:.4f} |\n"
        f"| URL钓鱼概率 | {url_prob:.4f} |\n"
        f"| 附件威胁等级 | {attach.get('threat_level', 'unknown')} |\n\n"
        "## 4. 关键证据与判定依据\n"
        f"{indicators_md}\n\n"
        "### 4.1 URL样本概览\n"
        f"{url_preview}\n\n"
        "## 5. 业务影响评估\n"
        f"{impact_text}\n\n"
        "## 6. 处置与加固建议\n"
        f"{rec_md}\n\n"
        "## 7. 复核结论与后续动作\n"
        f"{review_text}\n\n"
        "## 8. 模型输出快照\n"
        "```json\n"
        f"{snapshot_text}\n"
        "```\n"
    )



def make_llm_report_node(llm):
    def llm_report(state: EmailAnalysisState):
        enrich = {}
        try:
            enrich = _request_structured_sections(llm, state)
        except Exception:
            enrich = {}
        report = _build_fixed_markdown(state, enrich)

        return {
            "llm_report": report,
            "execution_trace": state["execution_trace"] + ["llm_report"],
        }

    return llm_report
