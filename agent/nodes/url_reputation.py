import joblib,os
from state.state import EmailAnalysisState

def analyze_url_reputation(state: EmailAnalysisState):
    """
    Node: 使用模型来预测 URL 是否恶意
    """
    print("加载模型")
    phish_url_model = open('./models/phishing_url.pkl', 'rb')
    phish_url_model_ls = joblib.load(phish_url_model)
    urls = state.get("urls", [])
    print("进行URL分析...")
    print(urls)
    url_analysis = dict()
    for url in urls:
        print("分析URL:", url)
        prediction = phish_url_model_ls.predict_proba([url])[0]
        url_analysis[url] = {
            "phishing_probability": float(prediction[0]),
            "legitimate_probability": float(prediction[1])
        }
        print("URL分析结果:", url_analysis[url])
    print("所有的URL分析完成：", url_analysis)
    print("计算最大恶意可能性...")
    url_analysis["max_possibility"] = max([url_analysis[url]["phishing_probability"] for url in urls])
    print("最大恶意可能性:", url_analysis["max_possibility"])
    return {
        "url_analysis": url_analysis,
        "execution_trace": state["execution_trace"] + ["analyze_url_reputation"]
    }