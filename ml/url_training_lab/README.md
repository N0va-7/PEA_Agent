# URL Training Lab

这个目录是独立实验区，用来单独优化 URL 恶意检测，不改原有 `ml/training/` 和线上产物。

## 现状判断

当前线上 URL 产物实际是：

- `CountVectorizer(word unigram) + LogisticRegression`

这不是错误方案，但它只适合作为 baseline。对 URL 这种强结构化短文本，误报高时通常说明这几个问题至少中了一个：

- 词级特征太粗，丢掉了很多局部模式。
- 没有 host/path/query 的词法特征。
- 阈值没有单独围绕 FPR 做验证集选择。
- 训练集和真实线上 benign URL 分布不一致。

## 这个实验区提供什么

- `benchmark.py`
  - 对比 4 种 URL 模型方案。
  - 默认以“满足 FPR 上限后尽量保留 F1”为选阈值策略。
- `train_candidate.py`
  - 训练选定候选模型。
  - 导出独立 joblib 和报告，不覆盖原有 artifact。
- `features.py`
  - URL 词法特征抽取。

## 候选模型

- `legacy_word_logreg`
  - 复刻当前线上思路，作为 baseline。
- `current_char_sgd_balanced`
  - 类似当前主项目保留的字符级 URL 建模思路，但使用 SGD 作为更轻的对照组。
- `char_tfidf_logreg`
  - 更稳的字符级 TF-IDF + LogisticRegression。
- `hybrid_char_lex_logreg`
  - 字符级 TF-IDF + 词法特征，优先用于降低误报。

## 为什么保留 hybrid 作为候选

误报高时，单纯依赖 `login`、`secure`、`account` 这类 token 容易把正常登录页打成恶意。hybrid 方法能同时看：

- 字符局部模式
- host 层级和长度
- path/query 复杂度
- 是否是 IP host
- 是否是短链
- suspicious token 命中数
- 熵和特殊字符比例

这比纯 bag-of-words 更适合 URL。

不过最终是否优于纯字符模型，不要靠直觉定，先跑 `benchmark.py`。这轮公开样本上，字符级 TF-IDF + SGD 的表现比 hybrid 更好。

## 用法

先跑基准：

```bash
./.py311/bin/python ml/url_training_lab/benchmark.py --max-rows 120000 --output-json /tmp/url_benchmark.json
```

再单独训练候选模型：

```bash
./.py311/bin/python ml/url_training_lab/train_candidate.py --candidate hybrid_char_lex_logreg --max-rows 120000
```
