import os

import requests

from state.state import EmailAnalysisState

def analyze_attachment_reputation(state: EmailAnalysisState):
    """
    Node: 调用微步 API 来分析附件的威胁情报
    :param state:
    :return:
    """
    print("\n=== 附件威胁情报分析 ===")
    attachment_analysis = dict()
    # 调用微步 API 分析附件威胁情报
    url = 'https://api.threatbook.cn/v3/file/upload'
    report_url = 'https://api.threatbook.cn/v3/file/report'
    fields = {
        'apikey': '484f3328c8b7483187361504a904d0682a2c90a05257420a8147fc42e9813401',
        'run_time': 60
      }
    file_dir = './uploads/'
    print("发现附件列表:")
    attachments = state.get("attachments", [])
    print(attachments)
    for item in attachments:
        file_name = item['filename']
        files = {
            'file': (file_name, open(os.path.join(file_dir, file_name), 'rb'))
        }
        try:
            print("提交附件:", file_name)
            response = requests.post(url, data=fields, files=files)
            upload_result = response.json()
            if upload_result['response_code'] != 0:
                print(f"{file_name} 上传失败: {upload_result['verbose_msg']}")
                continue
            print("成功上传，获取资源标识")
            resource = upload_result['data']["sha256"]
            from time import sleep
            sleep(10)  # 等待一段时间以确保文件分析完成
        except Exception as e:
            print(f"{file_name} 上传异常: {str(e)}")
            continue
        # 获取信誉报告
        params = {
            'apikey': '484f3328c8b7483187361504a904d0682a2c90a05257420a8147fc42e9813401',
            'resource': f'{resource}'
        }
        try:
            print("获取报告")
            response = requests.get(report_url, params=params)
            report_result = response.json()
            if report_result['response_code'] != 0:
                print(f"{file_name} 报告获取失败: {report_result['verbose_msg']}")
                continue
            print("成功获取报告，解析结果")
            data = report_result['data']
            summary = data['summary']
            threat_level = summary['threat_level']  # 威胁等级(malicious 恶意, suspicious 可疑, clean 安全, unknown 未知)
            malware_type = summary['malware_type']
            malware_family = summary['malware_family']
            multi_engines = summary['multi_engines']
            # 详细web报告
            permalink = data['permalink']
            attachment_report = {
                # 如果威胁等级是 malicious 或 suspicious，则标记为 bad，否则为 unknown
                'threat_level': "bad" if threat_level in ["malicious", "suspicious"] else 'unknown',
                'malware_type': malware_type,
                'malware_family': malware_family,
                'multi_engines': multi_engines,
                'permalink': permalink
            }
            print("附件报告:", attachment_report)
            attachment_analysis[file_name] = attachment_report
            print("总分析结果更新:", attachment_analysis)
        except Exception as e:
            print(f"{file_name} 报告获取异常: {str(e)}")
            continue
    print("\n=== 附件分析总结 ===")
    ret = "unknown"
    # attachment_analysis["threat_level"] = "unknown"
    print(attachment_analysis)
    for file_name, report in attachment_analysis.items():
        print(f"附件 {file_name} 分析结果: 威胁等级={report['threat_level']}, 报告链接={report['permalink']}")
        # 如果存在恶意附件，则标记整体状态为恶意
        if report['threat_level'] == 'bad':
            ret = "bad"
            break
    attachment_analysis["threat_level"] = ret
    return {
        "attachment_analysis": attachment_analysis,
        "execution_trace": state["execution_trace"] + ["analyze_attachment_reputation"]
    }
