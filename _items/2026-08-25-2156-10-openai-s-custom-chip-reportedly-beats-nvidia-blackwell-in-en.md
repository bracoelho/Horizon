---
layout: item
title: "OpenAI's Custom Chip Reportedly Beats Nvidia Blackwell in Tests"
date: 2026-08-25 21:56:22 +0000
lang: en
theme: business-markets
theme_name: "Business & Markets"
score: 8.0
link: "https://newsletter.semianalysis.com/p/openai-jalapeno-better-than-nvidia"
source: "bmulholland"
edition_url: "/2026/08/25/2156-summary-en.html"
edition_title: "2026-08-25 21:56 UTC"
enriched: true
---
Bloomberg reported on 25 August 2026 that OpenAI&\#x27;s in-development custom AI chip, referred to as Jalapeño, outperformed Nvidia&\#x27;s Blackwell processors in internal testing. The report was covered in a SemiAnalysis newsletter piece that frames the chip as a step toward reduced Nvidia dependency for OpenAI. No independent verification of the benchmark results has been published, and details on chip scale, deployment timeline, production partners, and actual cost or performance figures were not disclosed in the available reporting. The claim originates from OpenAI&\#x27;s own internal tests as relayed through Bloomberg, not from a third-party audit or public technical specification.

hackernews · bmulholland · Aug 25, 14:06 · [Discussion](https://news.ycombinator.com/item?id=49434378)

**「Market context」** OpenAI currently depends heavily on Nvidia GPUs, including Blackwell-generation hardware, to train and serve its models, a dependency shared across most large AI labs. Other hyperscalers have already moved toward custom silicon, including Google&\#x27;s TPUs and Amazon&\#x27;s Trainium chips, partly to reduce reliance on Nvidia&\#x27;s pricing and supply constraints. Nvidia&\#x27;s dominant position in AI accelerators has given it substantial pricing power and made GPU supply concentration a recognized risk factor for any organization building on top of major AI labs&\#x27; infrastructure.

**「Who gains and who loses leverage」** If OpenAI can shift meaningful inference workload onto its own chips, it gains negotiating leverage over Nvidia on pricing and allocation, and it reduces exposure to Nvidia supply constraints during periods of high demand. Nvidia loses some pricing power with one of its largest and most visible customers, which could pressure margins if other labs follow the same path, echoing the earlier moves by Google and Amazon. For buyers and enterprises building on OpenAI&\#x27;s models, this could eventually translate into lower per-token costs if the chip performs as claimed at scale, but the uncertainty hinges on whether the internal benchmark holds up under independent testing, whether the chip can be manufactured and deployed at the volume needed to matter, and how quickly OpenAI can integrate it into production serving without disrupting existing Nvidia-based capacity. Organizations with high-volume dependency on OpenAI&\#x27;s API should treat this as an early signal rather than a basis for near-term cost planning, since no confirmed timeline or pricing impact has been disclosed.

**「Practitioner reaction」** One commenter with domain interest suggested that at OpenAI&\#x27;s scale, baking specific model weights directly into custom silicon could pay for itself given how long some older models like GPT-OSS 120b remain in active use, since a $100M chip run offering 10x speed and cost improvements would be economical if useful for long enough. Others compared today&\#x27;s inference chip race to the early GPU market rivalries of the 3dfx and PowerVR era, questioning whether a dominant player will emerge, while one noted that continued hardware gains make further declines in token pricing hard to avoid.

**Tags**: `#custom silicon`, `#Nvidia dependency`, `#OpenAI infrastructure`, `#inference chips`, `#AI hardware competition`
