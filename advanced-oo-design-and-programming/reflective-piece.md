# Reflective piece — Advanced Object-Oriented Design and Programming

*Sections 1–2 of my end-of-module submission. The Capstone tasks it refers to are on the [Capstone Project](capstone-project/) page.*

## Introduction

As the written part of my e-Portfolio for this module, this document is in two sections. The first offers a reflective account of my learning and is structured around Gibbs’ (1988) reflective cycle. I have also made use of Kolb’s (1984) experiential learning cycle, the Johari Window (Luft and Ingham, 1955) and Bloom’s revised taxonomy (Anderson and Krathwohl, 2001) as further lenses to provide what Gibbs on his own does not.
The second section, the Appendix, is a verbatim copy from my e-Portfolio of the four Capstone Project tasks: Task 1, a summary of the learning outcomes; Task 2, the artefacts with critical commentary; Task 3, a reflection on skills developed; and Task 4, my professional development plan.
These artefacts are all from a single project that has been in progress, a thread-safe banking system in Python. What started as an individual coding exercise was put through the design-pattern units and became a payment service complete with pluggable pricing rules, security and audit layers, reporting visitors and an AI fraud-screening provider that is swappable, versioned and testable without a live model. I have chosen to build one system end to end as opposed to a collection of unconnected demos so as to observe how patterns interact and where their costs lie, something isolated examples will not show.



## A reflective account of my learning journey


### On the choice of framework

I put Gibbs’ (1988) cycle to use for its six stages, which have the effect of making me put some distance between what occurred, my feelings about it and my present thinking. That was a discipline I did not have at the outset of the module when my “reflections” were little more than progress reports. For the rest I have found that Kolb (1984) will tell me how the learning took place; the Johari Window puts a name to the things in my practice others can see but I cannot; and Bloom’s revised taxonomy provides the words to describe the level of thought I have arrived at as opposed to just saying I “understood”.


### Description

Up until this module my object-oriented coding was an exercise in putting functions into files; I could recite the four pillars and made too much of inheritance. The module set me three tasks I had not done right before: to write and validate concurrent code, to pick design patterns on their merits and not out of habit, and to design for a system with machine-learning components outside my control. The first turning point came with the individual exercise of a thread-safe bank with transfers free of deadlock. The second was the design-pattern units and the Capstone Project where I put Strategy, Decorator, Visitor and Abstract Factory to work on the same bank.


### Feelings

The strongest emotions were stirred by the concurrency exercise. My initial implementation of the transfer deadlocked in a manner I could not replicate at will and for two evenings I was left with the frustration of a bug that seems to show itself only when unobserved. Then I put together a script with the sole aim of breaking the system and deliberately reproduced it. The frustration gave way to the satisfaction of being able to put forward why the code worked rather than merely hope it did. A different kind of discomfort set in later with the first draft of my Visitor artefact when I had to go back and edit the account classes I had put through their paces. It felt as if the pattern I had put in place to shield them was the very reason I was having to touch them. In the event that was instructive.


### Evaluation

The change from writing code to making a case for it went well. I put four locking mechanisms head to head in a table for the coding exercise and put aside three with cause; in the Capstone I wrote a paragraph on the trade-offs for every pattern before I got to the class. I was moved in that direction by formative feedback and the seminar on the Capstone submission. The advice that “a screenshot without commentary is not evidence” has altered how I put everything in the Appendix. Time was less of a friend. I was off by a factor of two or so on the testing required for the AI-dependent part because one does not normally have to test against a collaborator, in this case a remote model, that is not in one’s environment. Some of my early posts on the discussion forum were more descriptive than they should have been; seeing peers question a pattern instead of expounding on it put the gap in perspective.


### Analysis

Kolb’s cycle makes sense of why the deadlock bug was a better teacher than the lectures on the subject. The lectures were abstract conceptualisation without the hard experience; the bug provided that and the failing script allowed for some reflective observation, while the fix with ordered-locking was active experimentation to close the loop. I now put that loop in place on purpose: with each Capstone pattern I put down the naïve version first so the benefit is something I have seen and not just read.
As for the unease with the Visitor, the Johari Window is the best way to view it. My “open” area was the fact that Visitor keeps algorithms and structure apart. What was “blind” to me, though the tutor saw it in his feedback, was that I was treating every pattern as a free good. I had not made it my own that the cost of adding element types is what you pay for the easy addition of operations with a Visitor. Once I put a name to that blind spot my rule for deciding changed. I now put to any pattern the question of which axis of change I am optimising and which I am making difficult. It is the most portable thing I have from the module and is in every piece of commentary for Task 2.
Then there is the AI side of things. With a fraud model as a collaborator I cannot look at the source to know what it will do, so the object-oriented precepts I was familiar with, like depending on abstractions, are no longer a matter of style but the only means of having a system that is testable and auditable. To put it in Bloom’s language I have gone from applying dependency inversion because it is suggested to evaluating it as the way to have a receipt record which version of the model made a decision and to let a mock stand in for the real thing. The ethical dimension is plain: a hierarchy with a threshold built into a customer-segment subclass is one with bias built in, and a decision you cannot trace to a model version is not one you can audit.


### Conclusion

I came to the module knowing how to talk about object-oriented principles and patterns. I can leave it having justified a pattern over another, designed code to allow a mock to replace an AI dependency that is not on hand and been critical of my own designs for over-engineering. Where I have improved the most is in the reflective judgement of cost, the one capability I was short of; I know when an abstraction has earned its keep. I am still wanting in depth when it comes to production-scale AI-aware architecture: my Model Registry and Feature Store are true to the concepts but in-memory and I have not run a real one. I have also learned my own ways of learning: I must make something fail to be sure I have it and should allow time for that instead of regarding it as a diversion.


### Action plan

There are three parts to my plan, the details of which including benchmarks and dates can be found in Task 4. The first is to put more depth into an AI-aware architecture: I will do this by way of an applied project that builds a registry and feature store with MLflow, as well as through a closer look at the ML-systems literature I have only sampled in passing here. Second, I intend to make the testing of intelligent systems more robust. That means learning property-based testing with Hypothesis to produce edge cases instead of guessing at them, and being critical in the use of AI for test generation, treating it as a way to put forward candidates for my own assessment rather than as a substitute. Third, I will give form to the ethical side of things by aligning my design checklist (covering explainable decisions, versioned models and an unbiased type system) with the BCS Code of Conduct and SFIA framework, and by securing a mentor with experience of putting AI-integrated systems through a regulatory audit. At the close of every module from now on I will go over this plan again, making the Gibbs cycle a matter of habit as was intended, not a single exercise.

## References

Anderson, L.W. and Krathwohl, D.R. (eds) (2001) *A taxonomy for learning, teaching, and assessing: a revision of Bloom’s taxonomy of educational objectives*. New York: Longman.

Gibbs, G. (1988) *Learning by doing: a guide to teaching and learning methods*. Oxford: Further Education Unit, Oxford Polytechnic.

Kolb, D.A. (1984) *Experiential learning: experience as the source of learning and development*. Englewood Cliffs, NJ: Prentice-Hall.

Luft, J. and Ingham, H. (1955) ‘The Johari Window: a graphic model of interpersonal awareness’, *Proceedings of the Western Training Laboratory in Group Development*. Los Angeles: University of California.
