# JARVIS v4.2 — Android

## Estrutura

- `main.py` — aplicativo completo.
- `buildozer.spec` — configuração correta do Buildozer.

## Gerar APK

No Linux/WSL:

```bash
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev cmake libffi-dev libssl-dev
python3 -m pip install --upgrade pip
python3 -m pip install buildozer cython
cd JARVIS_v4_2_ANDROID
buildozer -v android debug
```

O APK normalmente será colocado em `bin/`.

## Android

O projeto pede Android API 35, mínimo 24 e arquitetura arm64-v8a.

## Gemini

Abra `CONFIG` no aplicativo e informe sua própria chave de API. A chave é salva no armazenamento privado do aplicativo.

O aplicativo também funciona sem Gemini, com calculadora, tarefas, finanças, memória e pesquisa web.

## Observação

A configuração do Buildozer não fica dentro do `main.py`. Ela precisa estar no arquivo `buildozer.spec`.

## Compilar pelo celular

Você pode colocar esta pasta em um repositório do GitHub pelo navegador/app do GitHub.
Depois abra **Actions → Build JARVIS APK → Run workflow**.

Quando terminar, o GitHub disponibiliza o APK como artefato para baixar.

