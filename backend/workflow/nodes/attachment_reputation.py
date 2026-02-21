from time import sleep

import requests

from backend.workflow.state import EmailAnalysisState



def make_attachment_reputation_node(threatbook_api_key: str):
    upload_url = "https://api.threatbook.cn/v3/file/upload"
    report_url = "https://api.threatbook.cn/v3/file/report"

    def analyze_attachment_reputation(state: EmailAnalysisState):
        attachments = state.get("attachments", [])
        attachment_analysis = {}

        if not attachments:
            return {
                "attachment_analysis": {"threat_level": "unknown"},
                "execution_trace": state["execution_trace"] + ["analyze_attachment_reputation"],
            }

        if not threatbook_api_key:
            for item in attachments:
                attachment_analysis[item["filename"]] = {
                    "threat_level": "unknown",
                    "malware_type": "unknown",
                    "malware_family": "unknown",
                    "multi_engines": "0/0",
                    "permalink": "",
                }
            attachment_analysis["threat_level"] = "unknown"
            return {
                "attachment_analysis": attachment_analysis,
                "execution_trace": state["execution_trace"] + ["analyze_attachment_reputation"],
            }

        for item in attachments:
            file_name = item["filename"]
            stored_path = item.get("stored_path")
            try:
                with open(stored_path, "rb") as fh:
                    files = {"file": (file_name, fh)}
                    fields = {"apikey": threatbook_api_key, "run_time": 60}
                    response = requests.post(upload_url, data=fields, files=files, timeout=45)
                upload_result = response.json()
                if upload_result.get("response_code") != 0:
                    attachment_analysis[file_name] = {
                        "threat_level": "unknown",
                        "malware_type": "unknown",
                        "malware_family": "unknown",
                        "multi_engines": "0/0",
                        "permalink": "",
                    }
                    continue

                resource = upload_result["data"]["sha256"]
                sleep(10)

                params = {"apikey": threatbook_api_key, "resource": resource}
                response = requests.get(report_url, params=params, timeout=45)
                report_result = response.json()
                if report_result.get("response_code") != 0:
                    attachment_analysis[file_name] = {
                        "threat_level": "unknown",
                        "malware_type": "unknown",
                        "malware_family": "unknown",
                        "multi_engines": "0/0",
                        "permalink": "",
                    }
                    continue

                data = report_result["data"]
                summary = data["summary"]
                threat_level = summary.get("threat_level", "unknown")
                attachment_analysis[file_name] = {
                    "threat_level": "bad" if threat_level in ["malicious", "suspicious"] else "unknown",
                    "malware_type": summary.get("malware_type", ""),
                    "malware_family": summary.get("malware_family", ""),
                    "multi_engines": summary.get("multi_engines", ""),
                    "permalink": data.get("permalink", ""),
                }
            except Exception:
                attachment_analysis[file_name] = {
                    "threat_level": "unknown",
                    "malware_type": "unknown",
                    "malware_family": "unknown",
                    "multi_engines": "0/0",
                    "permalink": "",
                }

        aggregate = "unknown"
        for _, report in attachment_analysis.items():
            if isinstance(report, dict) and report.get("threat_level") == "bad":
                aggregate = "bad"
                break
        attachment_analysis["threat_level"] = aggregate

        return {
            "attachment_analysis": attachment_analysis,
            "execution_trace": state["execution_trace"] + ["analyze_attachment_reputation"],
        }

    return analyze_attachment_reputation
