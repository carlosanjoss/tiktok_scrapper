[![Twitter: romy](https://img.shields.io/twitter/follow/RomySihananda)](https://twitter.com/RomySihananda)

# tiktok-comment-scrapper

![](https://raw.githubusercontent.com/RomySaputraSihananda/RomySaputraSihananda/main/images/GA-U-u2bsAApmn9.jpeg)
Descobre vídeos publicados por perfis do TikTok, coleta os comentários e,
opcionalmente, baixa os arquivos MP4 e seus metadados.

## Requirements

- **Python >= 3.11.4**
- **Requests >= 2.31.0**
- **yt-dlp** e **curl-cffi** para descobrir e baixar vídeos
- **Playwright** como alternativa quando a descoberta principal falhar

## Installation

```sh
# Clonig Repository
git clone https://github.com/romysaputrasihananda/tiktok-comment-scrapper

# Change Directory
cd tiktok-comment-scrapper

# Create Virtual Environment (Optional)
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

# Install Requirement
pip install -r requirements.txt
```

No Windows deste projeto, a instalação já está pronta em `.venv`.

## Example Usages

### Single video

```sh
python main.py --aweme_id=7170139292767882522 --output=data
```

`--aweme_id` accepts a raw id, a full video URL or a short share link (`vm.tiktok.com/...`).

### Batch collection from a txt file

Put one link (or id) per line in `links.txt`, at the project root (a template is created for you, and it's git-ignored since it usually holds the specific videos you're researching):

```
# links.txt
https://www.tiktok.com/@usuario/video/7418294751977327878
https://vm.tiktok.com/XXXXXXXXX/
7626827891782798614
```

Then run without `--aweme_id` — the scraper picks up `links.txt` automatically:

```sh
python main.py --output=data
```

Each video is saved to `<output>/<aweme_id>.json`. Videos that already have a saved json in the output directory are skipped on re-runs, so a large batch can be stopped and resumed safely; pass `--overwrite` to force re-collecting them. `--delay` controls the wait (in seconds) between videos to avoid getting rate-limited.

### Perfis: vídeos e comentários

O arquivo `profiles.txt` já contém os perfis importados da planilha. Para cada
perfil, coletar os 20 vídeos mais recentes e seus comentários:

```sh
.venv\Scripts\python.exe main.py --videos-per-profile 20 --output data
```

Para também baixar os MP4 e o JSON de metadados de cada vídeo:

```sh
.venv\Scripts\python.exe main.py --videos-per-profile 20 --download-videos --output data
```

Para testar primeiro apenas a descoberta, sem comentários nem download:

```sh
.venv\Scripts\python.exe main.py --videos-per-profile 3 --discover-only --output data
```

O processamento pode ser interrompido e retomado. Comentários já salvos e
vídeos já baixados são reutilizados; use `--overwrite` para refazer. A estrutura
gerada é:

```text
data/
  profiles/
    usuario/
      _profile.json
      1234567890.json
      videos/
        1234567890.mp4
        1234567890.info.json
```

O TikTok pode limitar requisições. Use `--delay` entre vídeos e
`--profile-delay` entre perfis. Se a descoberta principal falhar, o programa
tenta o navegador local; `--headed` deixa essa janela visível para eventual
login ou CAPTCHA.

### Flags

| Flag | Alias | Description | Default |
| :--- | :---: | :--- | :---: |
| `--aweme_id` | | URL ou ID de um único vídeo | - |
| `--links-file` | `-l` | Arquivo com URLs/IDs de vídeos | `links.txt` |
| `--profiles-file` | `-p` | Arquivo com URLs de perfis | `profiles.txt` |
| `--videos-per-profile` | | Máximo de vídeos recentes por perfil | `20` |
| `--download-videos` | | Baixa MP4 e metadados dos vídeos | falso |
| `--discover-only` | | Salva somente a lista de vídeos descobertos | falso |
| `--headed` | | Exibe o navegador usado como alternativa | falso |
| `--output` | `-o` | Diretório de saída | `data` |
| `--overwrite` | | Refaz itens já salvos | falso |
| `--delay` | | Segundos entre vídeos | `1.5` |
| `--profile-delay` | | Segundos entre perfis | `5` |

## Sample Output

![](https://raw.githubusercontent.com/RomySaputraSihananda/RomySaputraSihananda/main/images/Screenshot_20231211_001804.png)

Each saved json is now wrapped with collection metadata, keeping the original `comments -> replies` hierarchy untouched:

```json
{
  "aweme_id": "7170139292767882522",
  "scraped_at": "2026-07-01T14:32:10Z",
  "total_comments": 2,
  "total_comments_with_replies": 3,
  "caption": "makk aku jadi animee🤩#faceplay #faceplayapp #anime #harem #xysryo ",
  "video_url": "https://t.tiktok.com/i18n/share/video/7170139292767882522/?_d=0&comment_author_id=6838487455625479169&mid=7157599449395496962&preview_pb=0&region=ID&share_comment_id=7310977412674093829&share_item_id=7170139292767882522&sharer_language=en&source=h5_t&u_code=0",
  "has_more": 0,
  "comments": [
    {
      "comment_id": "7310977412674093829",
      "username": "user760722966",
      "nickname": "rehan",
      "comment": "testing 😁😁",
      "create_time": "2023-12-10T21:46:36",
      "avatar": "https://p16-sign-useast2a.tiktokcdn.com/tos-useast2a-avt-0068-giso/f64f2c7df8a16098d3b3c80e958ffc52~c5_100x100.jpg?x-expires=1702306800&x-signature=KhUeuGmPAVij9A8gbgh7wK6rn98%3D",
      "total_reply": 0,
      "replies": []
    },
    {
      "comment_id": "7310977412674093830",
      "username": "user760722966",
      "nickname": "rehan",
      "comment": "bagus",
      "create_time": "2023-12-10T18:55:47",
      "avatar": "https://p16-sign-useast2a.tiktokcdn.com/tos-useast2a-avt-0068-giso/f64f2c7df8a16098d3b3c80e958ffc52~c5_100x100.jpg?x-expires=1702306800&x-signature=KhUeuGmPAVij9A8gbgh7wK6rn98%3D",
      "total_reply": 3,
      "replies": [
        {
          "comment_id": "7310977412674093831",
          "username": "ryo.syntax",
          "nickname": "Bukan Rio",
          "comment": "good game",
          "create_time": "2023-12-10T18:56:19",
          "avatar": "https://p16-sign-useast2a.tiktokcdn.com/tos-useast2a-avt-0068-giso/be4a9d0479f29d00cb3d06905ff5a972~c5_100x100.jpg?x-expires=1702306800&x-signature=IvkeSvXmvkmE0hZG5dtgpqcFn3A%3D",
          "total_reply": 0,
          "replies": []
        }
      ]
    }
  ]
}
```
