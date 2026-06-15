# Design: Terminal amigável com Zsh + Oh My Zsh no WSL/VSCode

**Data:** 2026-06-12
**Contexto:** Usuário Linux trabalhando em WSL Ubuntu no Windows, com terminal integrado do VSCode rodando bash por padrão. Objetivo: substituir bash por zsh com prompt rico, plugins de produtividade e fonte compatível com ícones.

---

## Componentes

### 1. Shell base
- Instalar `zsh` via `apt`
- Instalar **Oh My Zsh** via script curl oficial
- Definir zsh como shell padrão do usuário com `chsh -s $(which zsh)`

### 2. Tema — Powerlevel10k
- Clonar `romkatv/powerlevel10k` na pasta de temas do Oh My Zsh
- Definir `ZSH_THEME="powerlevel10k/powerlevel10k"` no `.zshrc`
- Na primeira abertura do terminal, o wizard interativo do p10k guia a configuração visual
- Exibe: git branch, status do venv Python, tempo de execução, código de saída do último comando

### 3. Fonte — FiraCode Nerd Font
- Baixar `FiraCodeNerdFont-Regular.ttf` do repositório oficial nerd-fonts
- Instalar no Windows (duplo clique no `.ttf` → "Instalar para todos os usuários")
- Necessária para os ícones do Powerlevel10k renderizarem corretamente no VSCode

### 4. Plugins
| Plugin | Instalação | Função |
|---|---|---|
| `git` | incluído no Oh My Zsh | aliases git (`gst`, `gco`, `gl`, etc.) |
| `zsh-autosuggestions` | clonar em `$ZSH_CUSTOM/plugins/` | sugere comandos do histórico enquanto digita |
| `zsh-syntax-highlighting` | clonar em `$ZSH_CUSTOM/plugins/` | colore comandos válidos/inválidos em tempo real |

Declarar os três em `plugins=(git zsh-autosuggestions zsh-syntax-highlighting)` no `.zshrc`.

### 5. VSCode settings.json
```json
"terminal.integrated.defaultProfile.linux": "zsh",
"terminal.integrated.fontFamily": "FiraCode Nerd Font"
```

---

## Fluxo de instalação

```
apt install zsh
  ↓
instalar Oh My Zsh (curl)
  ↓
clonar powerlevel10k → definir tema no .zshrc
  ↓
clonar zsh-autosuggestions e zsh-syntax-highlighting → declarar no .zshrc
  ↓
baixar e instalar FiraCode Nerd Font no Windows
  ↓
atualizar VSCode settings.json (defaultProfile + fontFamily)
  ↓
chsh -s $(which zsh)
  ↓
abrir novo terminal → wizard p10k
```

---

## Resultado esperado

Ao abrir o terminal integrado do VSCode:
- Shell é zsh
- Prompt rico com branch git, status do venv, tempo de execução
- Sugestão inline de comandos do histórico
- Colorização de sintaxe em tempo real
- Ícones e separadores renderizando corretamente
