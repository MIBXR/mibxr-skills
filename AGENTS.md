# Maintenance

- Skills live under `skills/`; each `SKILL.md` routes to its own references.
- Preserve portability: generic methods belong here, artwork and character-specific requirements belong in the work repository.
- After changing `compare_atlas.py`, run `python -m unittest discover -s tests`.
- After changing skill instructions, use the current official skill validator and evaluate meaningful workflow decisions. Keep current authorization boundaries and default automatic discovery.
- Installation and versioning are documented in `README.md`; tool and account credentials are configured in the receiving environment.
