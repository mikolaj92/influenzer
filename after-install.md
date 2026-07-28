# Start here

Run the local demo first. It needs no API keys and never posts to social networks.

```bash
hermes build-in-public --config config.yaml init
hermes build-in-public --config config.yaml validate
hermes build-in-public --config config.yaml collect --source manual --live
hermes build-in-public --config config.yaml render --format all --live
hermes build-in-public --config config.yaml weekly-recap --live
```

The first command writes `config.yaml` and a safe `notes/demo.md` sample. The live flags write local draft files only.

Expected output:

```text
output/cards/<stable-id>.json
output/drafts/<stable-id>.md
output/weekly/YYYY-WW.md
```

Replace `notes/demo.md` with your own local notes when the demo is clear. Generated drafts are review material, not publishing instructions.

CI-style checks:

```bash
python3 -m unittest discover -s tests
python3 tools/hygiene_check.py .
```
