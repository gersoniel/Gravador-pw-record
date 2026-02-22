🎙️ Mini Gravador de Áudio – PipeWire (pw-record)

Aplicativo gráfico simples em **Python + Tkinter** para gravação de áudio no Linux usando **PipeWire (`pw-record`)**.

O app permite:
- Definir o **nome do áudio**
- Escolher a **pasta onde o arquivo será salvo**
- **Gravar**, **Pausar / Continuar** e **Finalizar**
- Gerar arquivos `.wav`
- Empacotar como executável com **PyInstaller**
- (Opcional) Transcrever o áudio com **Whisper**

---

## 📸 Funcionalidades

- 🎙️ Grava áudio usando `pw-record`
- 📂 Seleção da pasta de destino
- ✏️ Definição do nome do arquivo
- ⏸️ Pausar e continuar gravação
- ⏹️ Finalizar gravação
- 🖥️ Interface gráfica (Tkinter)
- 📦 Geração de executável sem terminal

---

## 🧱 Requisitos

### Sistema
- Linux com **PipeWire**
- `pw-record` disponível no sistema

### Pacotes do sistema
```bash
sudo apt install python3 python3-tk pipewire
sudo apt install ffmpeg