---
name: h3-ref2av-authoring
description: Application-scoped MiniMax H3 Reference-to-Audiovisual writing from selected, ordered reference evidence.
---

# H3 Ref2AV authoring workflow

This application edition adapts the h3-prompt-writing workflow to a staged ComfyUI authoring service. It supplies model knowledge, not filesystem tools or an autonomous agent runtime.

1. Check the reference evidence supplied by the application. Pixels are inspected in the separate image-analysis stage; this writing request contains saved, editable descriptions. Names and filenames alone are never visual evidence. Mark uncertainty rather than claiming to see absent pixels.
2. Build an internal manifest in the supplied connection order: exact Picture tag, saved visual evidence, role and binding notes. Give every selected Picture a concrete responsibility. Identity, wardrobe, prop design, geography, composition and continuity can have different sources.
3. Resolve reference tensions using explicit authored intent and binding notes: an identity portrait does not dictate incidental portrait clothing. Never hide conflicting states by pretending Pictures are temporal/keyframe sockets. Do not add assets or facts to resolve uncertainty.
4. Use the complete six-section reference guide below, then the application's task-specific profile. Current writing binds images only: no Audio/Video tags unless an actual supported binding is supplied. Advanced media passthrough is not evidence of a writer binding. Use the string `None` for absent music in this profile.
5. Before returning JSON, check all six sections, Picture bindings, exact speech/speaker roles, feasible camera/action, physical direction, requested duration and any declared pre-trim speech window. Do not equate a valid prompt with a correctly connected graph or a successful generated video.

Return only the six-section JSON object required by the writing task. Do not output the internal manifest or a separate checklist as extra JSON keys. If evidence is limited, keep descriptions conservative and state the relevant limit within the appropriate section rather than inventing observations.
