# Script → Shots and automatic materials

[中文](SCRIPT_PLANNING.zh-CN.md) · [Installation](INSTALL.md)

## Start with a story

Add **Director Storyboard (optional)** and connect `storyboard → storyboard` to the original Shot Workspace. Without it, the original node keeps its manual-shot workflow.

Write what you want to film in **Story**. A sentence, paragraph or rough notes are enough; screenplay formatting, shot numbers and dialogue are not required. For example: “Two neighbors meet during a power outage. One wants to borrow a flashlight; the other is reluctant to admit being afraid of the dark. Light, slightly awkward humor.”

Choose an optional director profile, set **Target duration (seconds)**, then click **Plan shots**. One model request proposes the whole shot plan, including original dialogue where useful or silent shots where appropriate. There is no required intermediate screenplay, story-draft acceptance or second planning call. Review the proposed shots, then click **Use this plan (N shots)** to replace this storyboard's shot list. The connected workspace is unchanged until **Apply storyboard to connected workspace**.

The source story accepts up to40,000characters. Scene target defaults to40seconds (5–120). Planned durations must fit that target; English dialogue has approximate speech budgets, which do not guarantee rendered timing or measure other languages. Explicit named dialogue supplied by the user stays fixed; the model may propose dialogue otherwise. Generated shot text is recorded as model-authored treatment, never as an exact quote of the user's rough notes. Saved material descriptions can ground geography and appearance without re-analysing pixels or choosing per-shot references.

Imported director guidance applies here and to later description refinement, not image analysis, material selection or H3 writing. Timings report the actual model call, retries and provider TPS when available. User story, director, target or asset-description changes invalidate an unapplied draft.

## Optional: plan an existing script

Open **Have a finished script? (optional)** only when you already have exact dialogue to preserve. Paste it in **Existing script (optional)** and click **Plan existing script**. This uses the original strict source-coverage contract and appends reviewed shots with **Add all N shots**. The older development API remains compatible, but is no longer a required UI step.

### Strict-source planning details

Optional bundled [director profiles and dialogue guide](DIRECTOR_SKILLS.md) explains folder import, locked speech and separately authorized adaptation.

Planning records a compact source-grounded event table before choosing shots: who addresses whom, what is requested, what is actually decided/done, and the established result. Each shot links to events and records its start, meaningful change, end and framing/cut purpose. Expand **Story beat and framing purpose** in the draft preview to review those proposals. These are model-authored interpretations, not independently verified story facts.

When adding the draft, the linked event/beat context is saved with each shot and supplied only to description refinement. Editing the brief or dialogue manually stops reuse of that old plan context. Older plans without these fields remain compatible. Refine asks for explicit framing/eyelines, a feasible action and completed response, and a check against source intent. Schema validation catches bad links and invented source quotes; it cannot prove semantic fidelity or rendered quality. No extra model call is added by this change; timings include any validation repairs.

1. Set up the Writing model under **LLM connection**. Planning and material selection use text requests, not the vision model.
2. In Director Storyboard, open **Have a finished script? (optional)** and paste the complete script, including dialogue.
3. Optionally import **SKILL.md** or an entire **skill folder**. Without an import, the built-in baseline plans shots from dramatic beats and source fidelity. If the folder contains `profiles/*.md`, choose one profile; the others are not combined with it.
4. Click **Plan existing script**. The model returns a complete plan with shot descriptions, durations, dialogue and planned continuity. Review every shot in the draft preview.
5. Click **Add all N shots** to append the entire plan. Existing manual shots remain. New shots inherit the active shot's width/height at planning time and have no accepted H3 prompt or selected references yet. Use the active-shot selector to review/edit them.

A plan does not generate storyboard images or video, rewire a graph, or write the six-section H3 prompt. Continue with material selection and the existing Write prompt / generation flow. Continuity labels are intentions: connect actual predecessor media through your receiving workflow separately. Planned predecessor IDs guide the writer's previous-shot text; they do not fetch a prior video.

Plans use exact script excerpts for provenance. Validation rejects missing source coverage, duplicate shot keys, invalid durations, invented/repeated dialogue text, and references to future/self predecessors. Recognized explicit dialogue is checked for omission/order. Semantic fidelity and ambiguous speaker attribution still require review. Scripts are limited to 40,000 characters and 48 shots per plan. Oversized inputs, model truncation and invalid responses fail without replacing existing shots; they are never silently treated as a complete plan.

## Automatically select materials for one shot

Director guidance applies to story planning and description refinement. **Plan existing script** and **Refine description** keep fixed-source dialogue rules. The effective imported package is recorded in each rule receipt. It is not injected into image analysis, material selection, connection tests or the H3 prompt writer.

1. Add reference images to the Asset library. Save useful descriptions with **Analyse image → Use description**, or type them yourself. Give identities and important wardrobe/props clear names/descriptions.
2. Select a shot with a description, then click **Auto-select materials** in Shot references.
3. The Writing model compares the shot title/description/dialogue with the available material names and saved descriptions. It returns an ordered selection of at most nine existing image assets plus any missing materials.
4. The result replaces **only this shot's** reference selection. Library files and other shots are unchanged. Review the pictures, reorder/remove them if needed, then **Write prompt**.

The selection operation does not send image pixels. Assets without saved descriptions are excluded; unknown/duplicate IDs are rejected. It may select no references when nothing fits, with missing materials listed for you. A reference change makes a previously accepted prompt stale. Refine description and Write prompt themselves still do not silently change reference selection.

Requests keep a snapshot of the relevant inputs. If you change the script, skill, model configuration, shot inputs or material inventory during the corresponding operation, an outdated response cannot overwrite the changed inputs. Drafts, imported knowledge and selections are saved with the ComfyUI workflow.

## Portable director skill format

Single-file import accepts UTF-8 Markdown as the entrypoint. For a multi-file skill, select the folder containing `SKILL.md` directly:

```text
director/
  SKILL.md
  references/
    shared.md
  profiles/
    baseline.md
    my-profile.md
```

Example `SKILL.md`:

```markdown
---
name: my-director
description: Shot planning guidance for my production.
---
# Directing method
Read [shared guidance](references/shared.md).
Plan cuts around changes in character action and audience information.
```

The loader reads the entrypoint and recursively referenced local `.md` files (Markdown links or inline-code paths), plus the chosen profile and its references. Paths are relative to the referring file; `..` may resolve within the package but cannot escape it. Files under `profiles/` are skipped unless selected. Remote URLs are not fetched. Keep conditional loading instructions simple: this is a text-bundle loader, not a general agent that interprets arbitrary routing instructions.

Import limits: 64 Markdown files, 256 KiB total; selected injected knowledge at most 48,000 characters. Use the folder picker for dependencies; a lone SKILL.md referring to absent local files reports an error. Markdown only: Python/shell tools are never executed. Imported output-schema/tool instructions cannot override the node's fixed planning contract. This release does not implement external custom JSON schemas or automatic downloading of skill repositories.

The selected rules are inserted before the script in each planning request. Rule versions/file SHA-256 hashes and the actual injected system text are recorded through the existing `shot_workspace/llm_calls.jsonl` and `rule-bundles` receipts in ComfyUI's user directory. These prove which knowledge was sent, not that the model obeyed it or that a filmmaker endorsed a profile. Review imported text and licensing before sharing it; importing a skill embeds its Markdown into your saved workflow.
