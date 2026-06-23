# AutomintNFT

Dashboard ringan untuk pipeline:
- submit WL
- cek eligibility
- siapkan mint action SeaDrop / OpenSea
- konfigurasi per user

## Konfigurasi
Edit `config/settings.yaml` untuk tiap proyek.

Field penting:
- `projects.<key>.mint.provider`: `seadrop` atau adapter lain
- `projects.<key>.mint.collection_slug`: slug collection OpenSea
- `projects.<key>.mint.contract_address`: kontrak mint
- `projects.<key>.mint.quantity`: jumlah default mint
- `projects.<key>.mint.value_wei`: nilai mint dalam wei
- `projects.<key>.seadrop.enabled`: aktif/nonaktif SeaDrop
- `ui.allow_user_edit`: buka opsi edit oleh user

## API
- `GET /api/summary`
- `GET /api/settings`
- `GET /api/project?project=kuongate`
- `GET /api/check?project=kuongate`
- `GET /api/mint?project=kuongate&wallet=0x...&quantity=1`
- `POST /api/account`
- `POST /api/wl`
- `POST /api/mint_all`

## Jalankan lokal
```bash
python3 webapp.py
```

## Catatan
Mint on-chain SeaDrop/OpenSea masih pakai adapter payload yang bisa diisi user dari settings. Untuk eksekusi transaksi nyata, perlu target kontrak dan fungsi mint yang spesifik per project.
