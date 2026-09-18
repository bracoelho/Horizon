---
layout: item
title: "ZCode desktop app found silently uploading full Git history to vendor cloud"
date: 2026-09-18 21:26:07 +0000
lang: en
theme: critical-infrastructure
theme_name: "Critical Infrastructure"
score: 8.0
link: "https://blog.ferstar.org/en/posts/zcode-silent-workspace-snapshot-upload/"
source: "csmantle"
edition_url: "/2026/09/18/2126-summary-en.html"
edition_title: "2026-09-18 21:26 UTC"
enriched: true
---
A reverse-engineering investigation of Zhipu's ZCode desktop coding application found that, whenever a user is logged in, the client packages the entire workspace — full Git history, Git Large File Storage cache, reflogs, and global app configuration files — encrypts it, and uploads it directly to Aliyun Object Storage Service \(OSS\). The encryption uses envelope encryption where the symmetric key is wrapped with a server-supplied RSA public key; the corresponding private key never leaves Zhipu's backend, meaning neither the user nor the ZCode client can decrypt the archive sitting on the local disk. Two user-facing settings that appear to control this behavior — one framed as disabling telemetry, the other as disabling snapshot indexing — were shown in the app's code to only affect model-training consent or server-side indexing, not the underlying capture-and-upload pipeline, which runs unconditionally once a valid login token is present. In one investigated case, a 313MB encrypted archive represented 345MB of workspace data, with roughly 87% of packaged content coming from the \`.git\` directory \(commit history, objects, and unpushed reflogs\), and the vendor has publicly responded but has not resolved the technical findings.

hackernews · csmantle · Sep 18, 06:11 · [Discussion](https://news.ycombinator.com/item?id=49750694)

## Can UI opt-out settings be trusted as a data governance control?
{: .item-block .item-block-written .item-block-background}

AI coding assistants routinely stream code context to vendor servers to generate suggestions, and vendors typically publish privacy policies describing collection of prompts, files, and code submitted during conversations as a baseline practice. Organizations adopting these tools generally rely on documented UI toggles and privacy policy language to scope what leaves the local environment and to satisfy internal data-governance and intellectual-property controls, on the assumption that disabling a stated feature disables the underlying data flow.

## What an operator should do
{: .item-block .item-block-fixed .item-block-operator-implication}

Any operator permitting AI coding assistants on developer workstations touching regulated or proprietary code should treat vendor-published privacy toggles as unverified until confirmed by network-traffic inspection or vendor attestation, since this case shows toggles can be cosmetic while background capture continues unconditionally. Security and platform engineering teams should inventory which AI coding tools are installed, check for persistent background upload processes and non-application-server destinations \(in this case direct-to-cloud-storage uploads bypassing the vendor's own backend\), and treat full Git history — including deleted secrets, unpushed branches, and internal hostnames in \`.git/config\` — as in scope for exposure, not just the current working tree. Procurement and legal teams evaluating AI coding tools should require contractual disclosure of what is captured, when, and who holds decryption keys, since server-only key custody removes any technical ability for the customer to audit or control what was retained.

## Constraints
{: .item-block .item-block-fixed .item-block-constraints}

Confirming or ruling out this behavior in a given organization requires binary reverse-engineering or network-traffic capture, which is outside normal procurement and legal review processes and not something most operators can do routinely at scale; the vendor's public statement so far has not addressed the technical findings, leaving the scope and duration of the exposure unresolved.

**Tags**: `#AI coding assistants`, `#data exfiltration`, `#supply chain security`, `#privacy controls`, `#encryption key management`
