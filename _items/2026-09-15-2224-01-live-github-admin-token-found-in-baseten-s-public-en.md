---
layout: item
title: "Live GitHub admin token found in Baseten's public Docker image"
date: 2026-09-15 22:24:00 +0000
lang: en
theme: reliability-assurance
theme_name: "Reliability & Assurance"
score: 8.0
link: "https://www.strix.ai/blog/baseten-harbor-github-pat-takeover"
source: "bearsyankees"
edition_url: "/2026/09/15/2224-summary-en.html"
edition_title: "2026-09-15 22:24 UTC"
enriched: true
---
An autonomous security-testing agent \(Strix\), run without credentials or source code access against Baseten's public-facing infrastructure, discovered a public Harbor container registry project and pulled an image named baseten/baseten-app. Inside the image's build history metadata it found a live GitHub personal access token for an account called basetenbot, dating from a build in March 2023 but still valid when tested in July 2026. The token carried admin and push rights on Baseten's main product repository, its GitOps repository controlling cluster infrastructure, its Homebrew tap used for CLI distribution, and read/write access to further private repositories including one containing per-customer subdirectories; the researchers stopped after confirming access and reported the issue rather than acting on it further. Baseten, valued at $13 billion as an AI inference provider, made the registry project private within hours of disclosure and rotated the token by the following afternoon.

hackernews · bearsyankees · Sep 15, 18:11 · [Discussion](https://news.ycombinator.com/item?id=49716476)

## Docker image cleanup does not remove secrets from build history metadata
{: .item-block .item-block-written .item-block-background}

Organizations commonly assume that removing a credential file from a container image's final filesystem layers is sufficient to protect it, and that vendor security postures can be inferred from responsiveness and existing tooling rather than direct testing. Docker images retain a separate build history and config section, downloadable alongside the image, that can preserve build arguments and command values even after visible files are deleted, a behavior Docker itself documents as a risk.

## Who is exposed
{: .item-block .item-block-fixed .item-block-exposure}

This finding directly concerns organizations that send code, models, or customer data to Baseten's platform, since the exposed token had admin access to the repositories controlling Baseten's product code, cluster infrastructure \(GitOps\), and CLI distribution, plus a repository containing per-customer directories. More broadly, any organization building Docker images that pass secrets via ARG or inline shell commands \(rather than BuildKit secret mounts\) is exposed to the same class of issue and should audit both image layers and build history/config metadata, not just the final filesystem, for embedded credentials in any publicly or semi-publicly accessible registry.

## What reduces the risk
{: .item-block .item-block-fixed .item-block-mitigation}

Baseten remediated by making the Harbor registry project private and rotating the exposed token within about 18 hours of disclosure; the underlying fix for this class of issue is to use BuildKit secret mounts instead of persisted build arguments, followed by inspection of both image layers and build history, and revocation of any credential that may have been baked into previously distributed images, since changing the Dockerfile alone does not affect images already pulled by others.

**Tags**: `#supply-chain security`, `#secrets-in-containers`, `#vendor risk`, `#autonomous pentesting agents`, `#credential exposure`
