---
layout: item
title: "F2Asm Learns Exact SASS Assemblers for Blackwell and Rubin GPUs"
date: 2026-08-24 21:53:55 +0000
lang: en
theme: practice
theme_name: "Practice"
score: 8.0
link: "https://arxiv.org/abs/2608.20532"
source: "arXiv cs.LG"
edition_url: "/2026/08/24/2153-summary-en.html"
edition_title: "2026-08-24 21:53 UTC"
enriched: true
---
F2Asm is a new system that learns exact 128-bit SASS instruction encoders from paired disassembly and original CUBIN instruction words, using Gaussian elimination over the finite field F2 to build a compact basis, detect inconsistencies, and reject inputs outside the learned span. The authors trained encoders for NVIDIA Hopper SM90/SM90a, Blackwell SM100, and Rubin SM107 using 3,225 CUBINs drawn from pinned NVIDIA and third-party production libraries, CUDA 13.3 packages, and CUDA 13.4 Developer Preview archives. In round-trip tests, F2Asm reassembled the disassembled SASS for each CUBIN and every compared executable text section matched the original exactly. The authors describe it as the first system to learn SASS instruction encoders as vector-valued affine maps over F2, and the first open-source SASS assembler to support Rubin SM107.

rss · arXiv cs.LG · Aug 24, 04:00

**「Why this gap mattered」** NVIDIA ships an official SASS disassembler for its GPUs but no public assembler for recent data-center architectures, which has historically blocked controlled machine-code rewriting and forced anyone needing it to reverse-engineer instruction encodings by hand. SASS is the low-level assembly that CUDA binaries \(CUBINs\) compile down to, and precise control over it matters for kernel-level micro-optimization and low-level compiler research.

**「Practical effect for GPU tooling work」** Teams doing GPU compiler or kernel engineering can now assemble modified SASS back into valid CUBINs for Hopper, Blackwell, and Rubin without reverse-engineering instruction encodings by hand, since F2Asm is released as an open-source tool. This opens up workflows like hand-patching compiler output, building custom kernel optimization passes, or research on machine-code-level transformations that were previously blocked by the lack of a public assembler for these architectures. It is most directly useful for groups already working below the CUDA/PTX level, such as compiler backend developers or performance engineers instrumenting production kernels.

**「Limits to keep in mind」** The abstract is truncated and does not give per-architecture accuracy breakdowns or discuss failure modes beyond the round-trip matching described; validation is based on reassembling existing disassembled CUBINs rather than on arbitrary hand-authored SASS, and there is no evidence yet of adoption or use outside the authors&\#x27; own test corpus.

**Tags**: `#GPU architecture`, `#compiler tooling`, `#reverse engineering`, `#NVIDIA SASS`, `#open-source release`
