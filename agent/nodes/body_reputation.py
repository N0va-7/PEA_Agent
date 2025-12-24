import joblib,os
from state.state import EmailAnalysisState

def analyze_body_reputation(state: EmailAnalysisState):
    """
    Node: 使用模型来预测 邮件正文 是否恶意
    """

    print("加载模型")
    phish_body_model = open('./models/phishing_body.pkl', 'rb')
    phish_body_model_ls = joblib.load(phish_body_model)
    body = state.get("body", "")
    print("进行正文分析...")
    prediction = phish_body_model_ls.predict_proba([body])[0]
    body_analysis = {
        "phishing_probability": float(prediction[0]),
        "legitimate_probability": float(prediction[1])
    }
    print("正文分析结果:", body_analysis)
    # 如果不存在 urls，除非置信度很高，否则返回正常
    if state["urls"] is None or len(state["urls"]) == 0:
        print("正文中未发现URL，检查置信度...")
        if prediction[0] < 0.8:
            body_analysis["phishing_probability"] = 0.0
            body_analysis["legitimate_probability"] = 1.0
            return {
                "body_analysis": body_analysis,
                "execution_trace": state["execution_trace"] + ["analyze_body_reputation"]
            }
        return {
            "body_analysis": body_analysis,
            "execution_trace": state["execution_trace"] + ["analyze_body_reputation"]
        }
    print("正文中发现URL，保持结果不变")
    # urls 存在时，直接返回结果
    return {
        "body_analysis": body_analysis,
        "execution_trace": state["execution_trace"] + ["analyze_body_reputation"]
    }
