# Director profiles and dialogue

[中文](DIRECTOR_SKILLS.zh-CN.md) · [Script planning](SCRIPT_PLANNING.md)

The bundled [director-style skill folder](../authoring/skills/director-style/SKILL.md) contains a neutral baseline and Anderson-, Wilder-, Coen-, Fincher- and Ozu-inspired profiles. They are original technique interpretations, not official filmmaker skills or guarantees of a recognizable reproduction. Their focus is conversational tactics, subtext, cue-triggered listening and visible changes in the relationship, alongside framing and camera choices.

**Experimental:** model evaluation did not establish dependable improvement in dialogue quality or profile recognition. Some outputs invented facts; human review remains necessary.

## Import

1. In **Director Storyboard (optional)**, choose **Import skill folder**.
2. Select the repository's `authoring/skills/director-style` folder itself, with `SKILL.md` directly inside.
3. Select one profile. Review the complete plan before adding its shots.
4. Select materials and refine each shot as useful. Planning loads one compact packet; refinement loads shared rules and the selected profile. Other profiles and source articles are not injected.

This is an explicit import, not a silent new default. Already imported skills are stored snapshots: reimport this folder to receive changes.

Authorized dialogue-drafting examples are in a separate `dialogue/` folder and are excluded from normal planning/refinement. They are consulted only by a separate adaptation task. This keeps fixed-dialogue requests focused.

## Locked dialogue and authorized adaptation

Shot Workspace's existing **Plan all shots** and **Refine description** preserve the supplied dialogue. This skill does not override those checks. For locked lines it adjusts playable delivery, emphasis, listening, eyelines and coverage; it cannot make plain wording become a different screenplay just by adding style adjectives.

If the user explicitly authorizes adaptation, create a separate dialogue/script draft before planning. Draft from story facts and each speaker's objective; showing the original wording afterward for comparison can reduce line-by-line paraphrase. Keep original and rewritten versions together for review. Once chosen, the rewritten script becomes the source passed to **Plan all shots**, and its words are protected from that point onward. There is no automatic dialogue-rewrite button in this release.

For a rough idea, use **Story → Plan shots → Use this plan → Apply storyboard to connected workspace**. A finished script can use the optional **Plan existing script** path, which preserves its supplied dialogue.

Do not change a fixed outcome or add biography, props, precise times or actions to manufacture distinctiveness. Speech and a completed response must fit the proposed duration. Model-generated dialogue and descriptions still need human review; actual resemblance, acting and timing require rendered footage.

## Maintaining the pack

Edit `references/shared.md` and the relevant `profiles/*.md`, then run `python tools/build_director_packets.py` from the repository root. `--check` detects stale generated packets; requests never execute this script. Full-folder imports accept Markdown only.

[SOURCES.md](../authoring/skills/director-style/SOURCES.md) distinguishes primary contextual sources from our authored interpretations. Evaluation reports must distinguish syntax/contract compliance, story fidelity, conversational quality, style recognition and video execution.
# Optional planning node

Load director guidance in **Director Storyboard (optional)**, then connect and explicitly apply its reviewed plan to Shot Workspace. The original workspace can still be used without this node. Applied guidance is used for description refinement; it does not affect image analysis, automatic material selection or H3 prompt writing. See [planning workflow](SCRIPT_PLANNING.md).
