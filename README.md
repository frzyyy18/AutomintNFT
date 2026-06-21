# AutomintNFT

Website dashboard + pipeline untuk WL submit, eligibility check, dan mint orchestration.

## Local Run

```bash
python3 webapp.py
```

Buka:

- http://127.0.0.1:8080

## API

- `GET /api/summary`
- `GET /api/accounts`
- `GET /api/check?project=kuongate`
- `POST /api/account`
- `POST /api/wl`
- `POST /api/mint`
- `POST /api/pipeline`

## Notes

- Proyek awal: `kuongate`
- Data akun ada di `accounts/accounts.json`
- Data proyek ada di `config/settings.yaml`
