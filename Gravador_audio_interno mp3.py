import tkinter as tk
from tkinter import messagebox, filedialog
import subprocess
import os
import signal
import re

class GravadorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mini Gravador - PipeWire")
        self.root.geometry("520x220")
        self.root.resizable(False, False)

        # tenta definir o ícone da janela (fallback silencioso se não suportado)
        try:
            self.root.iconbitmap("Recorder.ico")
        except Exception:
            pass

        self.processo = None
        self.pausado = False
        self.arquivo_atual = None

        # pasta onde o arquivo será salvo (default = cwd)
        self.pasta_selecionada = os.getcwd()

        # ---- Interface ----
        tk.Label(root, text="Nome do áudio (sem extensão):").pack(pady=5)

        self.nome_audio = tk.Entry(root, width=60)
        self.nome_audio.pack(pady=5)

        # seleção de pasta de destino
        pasta_frame = tk.Frame(root)
        pasta_frame.pack(pady=5, fill="x", padx=10)
        tk.Label(pasta_frame, text="Salvar em:").grid(row=0, column=0, sticky="w")
        self.label_pasta = tk.Label(pasta_frame, text=self.pasta_selecionada, anchor="w", fg="gray25")
        self.label_pasta.grid(row=0, column=1, sticky="w", padx=(6,10))
        btn_pasta = tk.Button(pasta_frame, text="📁 Escolher pasta", command=self.selecionar_pasta)
        btn_pasta.grid(row=0, column=2, sticky="e")

        self.status = tk.Label(root, text="Status: parado", fg="blue")
        self.status.pack(pady=5)

        frame = tk.Frame(root)
        frame.pack(pady=10)

        self.btn_gravar = tk.Button(frame, text="🎙️ Gravar", width=12, command=self.gravar)
        self.btn_gravar.grid(row=0, column=0, padx=5)

        self.btn_pausar = tk.Button(frame, text="⏸️ Pausar", width=12, state="disabled", command=self.pausar)
        self.btn_pausar.grid(row=0, column=1, padx=5)

        self.btn_finalizar = tk.Button(frame, text="⏹️ Finalizar", width=12, state="disabled", command=self.finalizar)
        self.btn_finalizar.grid(row=0, column=2, padx=5)

    # ---- Funções ----
    def gravar(self):
        nome = self.nome_audio.get().strip()

        if not nome:
            messagebox.showerror("Erro", "Informe o nome do áudio.")
            return

        self.arquivo_wav = os.path.join(self.pasta_selecionada, f"{nome}.wav")
        self.arquivo_mp3 = os.path.join(self.pasta_selecionada, f"{nome}.mp3")

        if os.path.exists(self.arquivo_mp3):
            messagebox.showerror("Erro", "Esse arquivo já existe na pasta selecionada.")
            return

        try:
            self.processo = subprocess.Popen(
                ["pw-record", self.arquivo_wav],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            self.status.config(
                text=f"Status: gravando\n{self.arquivo_wav}",
                fg="green"
            )
            self.btn_gravar.config(state="disabled")
            self.btn_pausar.config(state="normal")
            self.btn_finalizar.config(state="normal")
            self.pausado = False

        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def pausar(self):
        if not self.processo:
            return

        if not self.pausado:
            os.kill(self.processo.pid, signal.SIGSTOP)
            self.status.config(text="Status: pausado", fg="orange")
            self.btn_pausar.config(text="▶️ Continuar")
            self.pausado = True
        else:
            os.kill(self.processo.pid, signal.SIGCONT)
            self.status.config(text="Status: gravando", fg="green")
            self.btn_pausar.config(text="⏸️ Pausar")
            self.pausado = False

    def finalizar(self):
        if self.processo:
            self.processo.terminate()
            self.processo.wait()

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", self.arquivo_wav,
                    "-codec:a", "libmp3lame",
                    "-qscale:a", "2",
                    self.arquivo_mp3
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )

            if os.path.exists(self.arquivo_wav):
                os.remove(self.arquivo_wav)

            self.status.config(
                text=f"Status: finalizado\n{self.arquivo_mp3}",
                fg="blue"
            )

            # opcional: chamar transcrição automática
            self.transcrever(self.arquivo_mp3)

        except Exception as e:
            messagebox.showerror("Erro ao converter MP3", str(e))

        self.btn_gravar.config(state="normal")
        self.btn_pausar.config(state="disabled", text="⏸️ Pausar")
        self.btn_finalizar.config(state="disabled")

        self.processo = None
        self.pausado = False

    def selecionar_pasta(self):
        pasta = filedialog.askdirectory(initialdir=self.pasta_selecionada, title="Selecione a pasta para salvar")
        if pasta:
            self.pasta_selecionada = pasta
            self.label_pasta.config(text=self.pasta_selecionada)

    def transcrever(self, arquivo_audio):
        """Transcreve `arquivo_audio` usando a biblioteca `whisper` se disponível.
        Salva o texto em um arquivo .txt ao lado do arquivo de áudio com o mesmo nome.
        """
        try:
            import whisper
        except Exception:
            messagebox.showinfo(
                "Transcrição",
                "Biblioteca 'whisper' não encontrada. Instale com:\n\n    pip install -U openai-whisper\n\nou escolha outra opção."
            )
            return

        try:
            # carrega modelo pequeno por padrão (ajustar se necessário)
            model = whisper.load_model("small")
            result = model.transcribe(arquivo_audio)
            texto = result.get("text", "").strip()

            # quebra de linha após cada ponto para evitar linhas muito longas
            texto = re.sub(r"\.\s*", ".\n", texto).strip()

            if texto:
                txt_path = os.path.splitext(arquivo_audio)[0] + ".txt"
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(texto)

                messagebox.showinfo("Transcrição", f"Transcrição salva em:\n{txt_path}")
            else:
                messagebox.showinfo("Transcrição", "Nenhum texto detectado na gravação.")

        except Exception as e:
            messagebox.showerror("Erro na transcrição", str(e))


# ---- Execução ----
if __name__ == "__main__":
    root = tk.Tk()
    app = GravadorApp(root)
    root.mainloop()
import tkinter as tk
from tkinter import messagebox, filedialog
import subprocess
import os
import signal
import re

class GravadorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mini Gravador - PipeWire")
        self.root.geometry("520x220")
        self.root.resizable(False, False)

        # tenta definir o ícone da janela (fallback silencioso se não suportado)
        try:
            self.root.iconbitmap("Recorder.ico")
        except Exception:
            pass

        self.processo = None
        self.pausado = False
        self.arquivo_atual = None

        # pasta onde o arquivo será salvo (default = cwd)
        self.pasta_selecionada = os.getcwd()

        # ---- Interface ----
        tk.Label(root, text="Nome do áudio (sem extensão):").pack(pady=5)

        self.nome_audio = tk.Entry(root, width=60)
        self.nome_audio.pack(pady=5)

        # seleção de pasta de destino
        pasta_frame = tk.Frame(root)
        pasta_frame.pack(pady=5, fill="x", padx=10)
        tk.Label(pasta_frame, text="Salvar em:").grid(row=0, column=0, sticky="w")
        self.label_pasta = tk.Label(pasta_frame, text=self.pasta_selecionada, anchor="w", fg="gray25")
        self.label_pasta.grid(row=0, column=1, sticky="w", padx=(6,10))
        btn_pasta = tk.Button(pasta_frame, text="📁 Escolher pasta", command=self.selecionar_pasta)
        btn_pasta.grid(row=0, column=2, sticky="e")

        self.status = tk.Label(root, text="Status: parado", fg="blue")
        self.status.pack(pady=5)

        frame = tk.Frame(root)
        frame.pack(pady=10)

        self.btn_gravar = tk.Button(frame, text="🎙️ Gravar", width=12, command=self.gravar)
        self.btn_gravar.grid(row=0, column=0, padx=5)

        self.btn_pausar = tk.Button(frame, text="⏸️ Pausar", width=12, state="disabled", command=self.pausar)
        self.btn_pausar.grid(row=0, column=1, padx=5)

        self.btn_finalizar = tk.Button(frame, text="⏹️ Finalizar", width=12, state="disabled", command=self.finalizar)
        self.btn_finalizar.grid(row=0, column=2, padx=5)

    # ---- Funções ----
    def gravar(self):
        nome = self.nome_audio.get().strip()

        if not nome:
            messagebox.showerror("Erro", "Informe o nome do áudio.")
            return

        self.arquivo_wav = os.path.join(self.pasta_selecionada, f"{nome}.wav")
        self.arquivo_mp3 = os.path.join(self.pasta_selecionada, f"{nome}.mp3")

        if os.path.exists(self.arquivo_mp3):
            messagebox.showerror("Erro", "Esse arquivo já existe na pasta selecionada.")
            return

        try:
            self.processo = subprocess.Popen(
                ["pw-record", self.arquivo_wav],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            self.status.config(
                text=f"Status: gravando\n{self.arquivo_wav}",
                fg="green"
            )
            self.btn_gravar.config(state="disabled")
            self.btn_pausar.config(state="normal")
            self.btn_finalizar.config(state="normal")
            self.pausado = False

        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def pausar(self):
        if not self.processo:
            return

        if not self.pausado:
            os.kill(self.processo.pid, signal.SIGSTOP)
            self.status.config(text="Status: pausado", fg="orange")
            self.btn_pausar.config(text="▶️ Continuar")
            self.pausado = True
        else:
            os.kill(self.processo.pid, signal.SIGCONT)
            self.status.config(text="Status: gravando", fg="green")
            self.btn_pausar.config(text="⏸️ Pausar")
            self.pausado = False

    def finalizar(self):
        if self.processo:
            self.processo.terminate()
            self.processo.wait()

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", self.arquivo_wav,
                    "-codec:a", "libmp3lame",
                    "-qscale:a", "2",
                    self.arquivo_mp3
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )

            if os.path.exists(self.arquivo_wav):
                os.remove(self.arquivo_wav)

            self.status.config(
                text=f"Status: finalizado\n{self.arquivo_mp3}",
                fg="blue"
            )

            # opcional: chamar transcrição automática
            # self.transcrever(self.arquivo_mp3)

        except Exception as e:
            messagebox.showerror("Erro ao converter MP3", str(e))

        self.btn_gravar.config(state="normal")
        self.btn_pausar.config(state="disabled", text="⏸️ Pausar")
        self.btn_finalizar.config(state="disabled")

        self.processo = None
        self.pausado = False

    def selecionar_pasta(self):
        pasta = filedialog.askdirectory(initialdir=self.pasta_selecionada, title="Selecione a pasta para salvar")
        if pasta:
            self.pasta_selecionada = pasta
            self.label_pasta.config(text=self.pasta_selecionada)

    def transcrever(self, arquivo_audio):
        """Transcreve `arquivo_audio` usando a biblioteca `whisper` se disponível.
        Salva o texto em um arquivo .txt ao lado do .wav com o mesmo nome.
        """
        try:
            import whisper
        except Exception:
            messagebox.showinfo(
                "Transcrição",
                "Biblioteca 'whisper' não encontrada. Instale com:\n\n    pip install -U openai-whisper\n\nou escolha outra opção."
            )
            return

        try:
            # carrega modelo pequeno por padrão (ajustar se necessário)
            model = whisper.load_model("small")
            result = model.transcribe(arquivo_audio)
            texto = result.get("text", "").strip()

            # quebra de linha após cada ponto para evitar linhas muito longas
            texto = re.sub(r"\.\s*", ".\n", texto).strip()

            if texto:
                txt_path = os.path.splitext(arquivo_audio)[0] + ".txt"
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(texto)

                messagebox.showinfo("Transcrição", f"Transcrição salva em:\n{txt_path}")
            else:
                messagebox.showinfo("Transcrição", "Nenhum texto detectado na gravação.")

        except Exception as e:
            messagebox.showerror("Erro na transcrição", str(e))


# ---- Execução ----
if __name__ == "__main__":
    root = tk.Tk()
    app = GravadorApp(root)
    root.mainloop()
