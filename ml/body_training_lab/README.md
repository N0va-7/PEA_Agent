# Body Training Lab

这个目录是邮件正文的独立实验区，不改原有 `ml/training/` 和线上模型。

## 目标

找出比现有正文训练更适合业务的方案，重点关注：

- 少误报
- 少漏报
- 训练和部署不要太重

## 当前旧方案

从 notebook 看，正文最早的主方案是：

- `TfidfVectorizer + RandomForestClassifier`
- `TfidfVectorizer + SVC`

从当前 `retrain_models.py` 看，后来切到了：

- `TfidfVectorizer(词 1-2 gram) + SGDClassifier(log_loss)`

## 这里对比哪些方案

- `legacy_tfidf_random_forest`
  - 接近旧 notebook 路线。
- `current_word_sgd_balanced`
  - 接近当前重训脚本路线。
- `word_tfidf_logreg`
  - 正文分类里很常见、很稳的 baseline。
- `word_char_tfidf_logreg`
  - 同时看正文里的“词”和“局部拼写模式”。

## 通俗理解

- `word` 特征：看邮件里说了哪些词、哪些短语。
- `char` 特征：看拼写细节、局部片段、奇怪写法。

邮件正文和 URL 不一样。正文更偏“语言内容”，所以通常：

- 先看词和短语最重要
- 再考虑字符片段补充

## 用法

先跑对比：

```bash
./.py311/bin/python ml/body_training_lab/benchmark.py --output-json /tmp/body_benchmark.json
```

再训练当前最优候选：

```bash
./.py311/bin/python ml/body_training_lab/train_candidate.py --candidate word_tfidf_logreg
```
