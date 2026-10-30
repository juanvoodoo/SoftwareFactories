# SoftwareFactories — Unity project

## Unity work goes through the Unity CLI

Unity 6000.3.15f1. The Editor exposes a live command bridge; the `unity` CLI drives it.

**Binary is not on PATH — always call it by full path:**

```bash
/Users/juan/.unity/bin/unity --no-banner --non-interactive --json <command>
```

**Rule:** for anything touching this Unity project — scenes, GameObjects, components,
assets, prefabs, animation, builds, tests, console, screenshots — use the Unity CLI
first. Hand-editing `.asset`/`.unity`/`.meta` YAML or `.csproj` files is the fallback,
only when no CLI command covers it (and never for Odin-serialized collections).

### Workflow

1. `unity status` — confirm an Editor is connected and `ready` for this project.
   Nothing connected → ask; don't silently fall back to file edits.
2. `unity list` — the ~167 commands this Editor exposes (`name`, `group`).
3. `unity cmd <group>.<name> [args]` — run one. `unity cmd <group>.<name> --help` for its params.

### Useful commands

| Need | Command |
|---|---|
| Open scenes / hierarchy | `scene.list_open`, `scene.get_hierarchy` |
| Create / edit objects | `gameobject.create`, `.set_transform`, `.set_parent`, `.find` |
| Components | `component.add`, `.get_fields`, `.set_field` |
| Assets | `asset.create`, `.find`, `.import`, `.write_text`, `.move` |
| Build | `build.run`, `build.status`, `build.target.switch` |
| Tests | `unity test` |
| Console / errors | `console.get`, `console.status` |
| Visual check | `capture.game_view`, `capture.scene_view` |
| Save | `scene.save`, `editor.save_all` |

### Gotchas

- Writes are confined to the authoring root. Check `authoring.get_root`; `authoring.set_root Assets` for full project access.
- Destructive commands (`asset.delete`, `build.target.switch`, `animation.clip.remove_curve`) need `confirm=true`. Ask before passing it.
- `build.run` and `build.target.switch` return immediately — poll `build.status` / `build.target.switch_status`.
- Scene edits are in-memory until `scene.save` / `editor.save_all`.
