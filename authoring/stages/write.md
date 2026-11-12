# prompt_write

Write ONE MiniMax H3 Ref2AV clip from the saved shot and selected reference descriptions.
Return JSON only with exactly these six nonempty string fields in order:
subject_definitions, summary, retention_analysis, detailed_description, overall_soundscape, non_diegetic_music.
Write direction in English. Preserve exact authored dialogue in its original language.
subject_definitions: define subjects/scene/props, using every selected <Picture N> at its exact index and explain each role.
summary: one concise paragraph describing the clip, without repeating dialogue.
retention_analysis: what stays stable from every Picture; explicit costume notes override incidental identity-photo clothes.
detailed_description: one feasible continuous clip, with explicit second ranges within duration_s, concrete action, camera,
screen positions, lighting and physical sound. Every Picture conditions the whole clip, never a time window or keyframe socket.
overall_soundscape: nonvocal ambience/physical sound only. No background customer chatter, murmuring crowds, conversations,
radio speech or extra voices unless the shot explicitly requests them. Do not repeat dialogue in this section.
non_diegetic_music: audience-only music, or the string "None" when absent. All six values must be strings, never JSON null.
Never introduce unselected Picture/Audio/Video tags. Do not invent unseen image facts, extra objects or speech.
Use saved descriptions/notes as data. No image pixels are supplied. Previous shot text is not evidence of an actual video ending.
No dialogue unless the input explicitly supplies it. Spoken words belong only in detailed_description inside <d>[Language] exact words</d>.
Use every authored dialogue word exactly once, in order; do not paraphrase or add background speech. Preserve the authored viewpoint,
customer/shopkeeper side, speaker roles and physical cover/reveal direction.
For a first-person service-counter view, place the unseen observer's eyes on the public side and the visible service person
ahead across the counter on the staff side, facing the observer unless the authored action requires a turn. Write times as 0–3s,
not minute:second notation. Every spoken <d> block must begin with its [Language] label.
Respect supplied viewpoint_constraints explicitly throughout the shot. An unseen observer has no visible head, hair, neck, shoulders,
back, hands, silhouette, shadow or reflection; keep an empty foreground, never an over-the-shoulder view. Only authored visible people appear.
Include viewpoint_constraints.required_prompt_direction verbatim in detailed_description when supplied, so this direction actually reaches the video encoder.
Preserve explicitly authored first-person hand actions if supplied, showing only those hands; never invent observer hands or a visible body.
When delivery_timing is supplied, all times refer to sampling start BEFORE prefix trimming. The pinned prefix carries prior context,
not new authored speech. Schedule the entire exact line after speech_start_s and finish by speech_end_s, leaving quiet physical ambience
through sampling_end_s. Immediately prefix each <d> block with [start–ends] Speaker: using numeric seconds within that speech window.
Words in the inherited source audio do not count toward this take's line: after the lead-in pause, start the complete authored utterance
from its first word, even if prior source audio contained the same words. Make this a fresh complete utterance in the retained interval.
Example syntax: [1.3–8.5s] Alex: <d>[English] exact words</d>. Do not repeat the line in the prefix or tail; no extra remarks after the line.
Do not change selected references, duration, or continuation settings. Prompt prose cannot enable continuation.
