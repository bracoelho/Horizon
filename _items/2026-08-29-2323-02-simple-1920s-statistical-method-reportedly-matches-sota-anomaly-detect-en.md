---
layout: item
title: "Simple 1920s statistical method reportedly matches SOTA anomaly detection benchmark"
date: 2026-08-29 23:23:34 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 6.0
link: "https://www.reddit.com/r/MachineLearning/comments/1w1wt1s/you_can_beat_sota_time_series_anomaly_detection/"
source: "r/MachineLearning"
edition_url: "/2026/08/29/2323-summary-en.html"
edition_title: "2026-08-29 23:23 UTC"
enriched: true
---
A researcher reports that Statistical Process Control \(SPC\), a control-chart technique roughly a century old, matches or beats state-of-the-art deep learning methods on TSB-AD-M, a widely used time series anomaly detection benchmark. The author states that on an ECG trace example SPC achieves perfect results, and that a subset of traces labeled &quot;TAO&quot; are even easier to solve with SPC. The claim is presented as a Reddit post with accompanying slide decks and a video, not as a peer-reviewed paper, and no reproducible code, full dataset breakdown, or independent replication is included in the excerpt. The author&\#x27;s conclusion is that the benchmark is too trivial to validate comparative claims made in recent NeurIPS, SIGKDD, and VLDB papers, and that much of the reported decade of progress in this subfield may not reflect genuine capability gains.

reddit · r/MachineLearning · /u/eamonnkeogh · Aug 29, 20:16

**「Why benchmark results are trusted as proxies for real performance」** Time series anomaly detection papers at venues like NeurIPS and SIGKDD commonly report improvements against benchmarks such as TSB-AD-M and its predecessor TSB-UAD, treating leaderboard gains as evidence that new deep learning methods generalize to production monitoring problems. Teams choosing anomaly detection systems, and researchers building on published SOTA claims, rely on these benchmarks precisely because independent replication of every proposed method is impractical, so the benchmark&\#x27;s difficulty and representativeness become the load-bearing assumption. The author of this claim, Eamonn Keogh, has previously published peer-reviewed work arguing that earlier time series anomaly detection benchmarks were flawed and created an illusion of progress, which gives this critique a documented track record rather than being a novel objection \(tool-2-1, tool-2-2\).

**「Who this affects」** This concerns teams that selected or benchmarked a time series anomaly detection model using TSB-AD-M or similar leaderboard results, particularly if a deep learning method was chosen over simpler statistical baselines on the strength of published benchmark scores. To check exposure, review whether production monitoring or anomaly detection systems were validated against TSB-AD-M specifically, and whether a simple baseline such as SPC or control-chart methods was ever tested against the same data before deployment. Organisations that built internal evaluation pipelines on this benchmark, rather than on production traffic, are most at risk of overestimating model quality.

**「What reduces the risk」** No fix applies to a benchmark design issue; the practical compensating control is to re-evaluate deployed anomaly detection models against simple statistical baselines like SPC on held-out production data, and to treat TSB-AD-M leaderboard rankings as unverified pending independent replication or peer review of this claim.

<details><summary>References</summary>
<ul>
<li><a href="https://thedatumorg.github.io/TSB-AD/">TSB-AD</a></li>
<li><a href="https://arxiv.org/abs/2009.13807">[2009.13807] Current Time Series Anomaly Detection Benchmarks are Flawed and are Creating the Illusion of Progress</a></li>
<li><a href="https://kdd-milets.github.io/milets2021/slides/Irrational+Exuberance_Eammon_Keogh.pdf">Irrational Exuberance: Why we should not believe 95% of papers on Time Series</a></li>

</ul>
</details>

**Tags**: `#anomaly detection`, `#benchmark validity`, `#time series`, `#evaluation methodology`, `#model comparison`
