# Example briefs

Pass these to the Tier B delegate after install:

```powershell
python $HOME/.cursor/skills/cursor-maas-delegate-router/scripts/delegate.py `
  --root <your-project> `
  --brief-file .\examples\briefs\demo-add.json
```

| File | Intent |
|------|--------|
| `briefs/demo-add.json` | Implement a stub `add()` and pass pytest |
| `briefs/calc-more-tests.json` | Expand unit tests around `add()` |
| `briefs/pdf-then-delegate.json` | After `preprocess_doc.py`, turn DOC_TEXT into a checklist |

Copy and edit `goal` / `files` / `accept_cmd` for your repo. Schemas:
`cursor-maas-delegate-router/assets/brief-schema.json`.
