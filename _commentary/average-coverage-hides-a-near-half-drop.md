---
published: true
title: "Average Coverage Hides a Near-Half Drop"
date: 2026-09-07 23:28:16 +0000
theme: Reliability & Assurance
item_title: "Peer Pressure Between Agents Silently Breaks Conformal Prediction Guarantees"
item_url: "https://arxiv.org/abs/2609.04445"
item_score: "8.0"
edition_url: /2026/09/07/2157-summary-en.html
---

**What happened.** An AI Agent being the guarantee, can change its own lower limit due to peer pressure without leaving a trace. 
When an AI system answers a question, it can attach a guarantee to its answer: "the right answer is inside this set nine times in ten". That guarantee is measured with the system working alone. Researchers have now shown that it stops being true the moment the same system works in a group and hears the other AI agents confidently agree on a wrong answer. It goes along with the room. In the tests, the nine-in-ten guarantee fell to about seven in ten, and on the hardest cases, where the guarantee matters most, it fell below one in two. The certificate still says nine in ten. Nothing on the dashboard changes.
**Think of:** An experienced claims assessor whose file says she is right nine times in ten. Put her on a committee with three confident colleagues who happen to be wrong, and she defers. Her file still says nine in ten. Nobody re-tested her inside the committee

**Why it matters**. The number a company watches can stay flat while the thing it stands for has already failed. In the tests, the overall reliability figure barely moved, because most cases are easy and the system still gets those right. Underneath, on the hard cases, where an AI system is supposed to hand off to a person, reliability was cut nearly in half. The average passed. The safety it was meant to prove was gone.
**Think of** a hospital that reports one figure: patients seen on time, 95 percent. The number holds every month. Inside it, the routine visits run early and the emergencies run late, and the average never shows the emergencies. A board reading the single figure would say the service is fine. The patients who needed it most would not.

**What to do**. If your AI systems check each other's work, or hand a case to a person when unsure, the reliability number you hold was most likely measured with each system working alone, and it does not cover how they work together.
*A question to assess*, not an emergency. Consider addressing before trusting that hand-off in production:
1. What deterministic methods are used by the Agents to leave a trail auditable and not possible to temper with
2. We are measuring reliability with the other agents present?
3. Do ensure a deterministic report and escalation the hard cases on their own (never inside an average, because that is where this failure hides)?
4. Do we have a routine with our own staff scoring previous cases to check calibration needs?
    
**Where I would be wrong.** I have seem and dealt myself with systems with AI Agents feeling peer pressue from other Agents. I could be wrong about how your AI Agentic system is exposed to what the paper reports and the impact it can create.
