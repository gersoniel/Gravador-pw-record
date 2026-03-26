import tkinter as tk
from tkinter import messagebox, filedialog
import subprocess
import os
import signal
import re
import json
import threading

class GravadorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mini Gravador - PipeWire")
        self.root.geometry("900x420")
        self.root.resizable(False, False)

        # tenta definir o ícone da janela (fallback silencioso se não suportado)
        try:
            self.root.iconbitmap("Recorder.ico")
        except Exception:
            pass

        self.processo = None
        self.pausado = False
        self.arquivo_atual = None
        self.transcrevendo = False
        self.thread_transcricao = None

        # pasta onde o arquivo será salvo (default = cwd)
        self.pasta_selecionada = os.getcwd()

        # obter entradas de áudio disponíveis
        self.obter_entradas()

        # ---- Interface ----
        tk.Label(root, text="Nome do áudio (sem extensão):").pack(pady=5)

        self.nome_audio = tk.Entry(root, width=60)
        self.nome_audio.pack(pady=5)

        # seleção de entrada de áudio
        entrada_frame = tk.Frame(root)
        entrada_frame.pack(pady=5, fill="x", padx=10)
        tk.Label(entrada_frame, text="Entrada de áudio:").grid(row=0, column=0, sticky="w")
        self.entrada_var = tk.StringVar()
        
        # Prepara lista de nomes para exibição
        self.entrada_opcoes = [f"{nome}" for nome, _ in self.entradas]
        if self.entrada_opcoes:
            self.entrada_var.set(self.entrada_opcoes[0])
        
        self.entrada_menu = tk.OptionMenu(entrada_frame, self.entrada_var, *self.entrada_opcoes)
        self.entrada_menu.grid(row=0, column=1, sticky="w", padx=(6,10))
        btn_atualizar = tk.Button(entrada_frame, text="🔄 Atualizar", command=self.atualizar_entradas)
        btn_atualizar.grid(row=0, column=2, sticky="e", padx=(0,10))

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

        # Checkbox para ativar/desativar transcrição automática
        self.transcricao_var = tk.BooleanVar(value=True)
        self.checkbox_transcrever = tk.Checkbutton(frame, text="📝 Transcrever (Whisper)", variable=self.transcricao_var)
        self.checkbox_transcrever.grid(row=1, column=0, columnspan=3, pady=10)

    # ---- Funções ----
    def obter_entradas(self):
        """Lista as entradas de áudio disponíveis no PipeWire."""
        self.entradas = []
        try:
            # Usa pactl para listar fontes de áudio disponíveis
            resultado = subprocess.run(
                ["pactl", "list", "short", "sources"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if resultado.returncode == 0:
                for linha in resultado.stdout.strip().split('\n'):
                    if linha.strip():
                        # Formato: ID    NAME    MODULE  PROPERTIES
                        partes = linha.split('\t')
                        if len(partes) >= 2:
                            entrada_id = partes[0].strip()
                            entrada_nome = partes[1].strip()
                            self.entradas.append((entrada_nome, entrada_id))
        except Exception:
            pass
        
        # Se não conseguir, detecta via pactl info
        if not self.entradas:
            try:
                resultado = subprocess.run(
                    ["pactl", "info"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if resultado.returncode == 0:
                    for linha in resultado.stdout.split('\n'):
                        if "Default Source" in linha:
                            # Extrai nome da fonte padrão
                            nome = linha.split(':')[1].strip()
                            self.entradas.append((nome, "default"))
            except Exception:
                pass
        
        # Se ainda não conseguir, usa entrada padrão
        if not self.entradas:
            self.entradas = [("Entrada padrão (default)", "default")]

    def atualizar_entradas(self):
        """Atualiza a lista de entradas de áudio disponíveis."""
        self.obter_entradas()
        menu = self.entrada_menu["menu"]
        menu.delete(0, "end")
        
        self.entrada_opcoes = [f"{nome}" for nome, _ in self.entradas]
        for opcao in self.entrada_opcoes:
            menu.add_command(label=opcao, command=lambda value=opcao: self.entrada_var.set(value))
        
        if self.entrada_opcoes:
            self.entrada_var.set(self.entrada_opcoes[0])
        
        messagebox.showinfo("Sucesso", f"{len(self.entradas)} entrada(s) de áudio detectada(s).")

    def gravar(self):
        nome = self.nome_audio.get().strip()

        if not nome:
            messagebox.showerror("Erro", "Informe o nome do áudio.")
            return

        entrada_selecionada = self.entrada_var.get()
        if not entrada_selecionada:
            messagebox.showerror("Erro", "Selecione uma entrada de áudio.")
            return

        self.arquivo_wav = os.path.join(self.pasta_selecionada, f"{nome}.wav")
        self.arquivo_mp3 = os.path.join(self.pasta_selecionada, f"{nome}.mp3")

        if os.path.exists(self.arquivo_mp3):
            messagebox.showerror("Erro", "Esse arquivo já existe na pasta selecionada.")
            return

        # Valida se ffmpeg está instalado
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=2)
        except FileNotFoundError:
            messagebox.showerror(
                "Erro",
                "ffmpeg não está instalado.\nInstale com: sudo apt install ffmpeg libmp3lame0"
            )
            return

        try:
            # Encontra o ID da entrada selecionada
            entrada_id = None
            for nome_entrada, id_entrada in self.entradas:
                if nome_entrada == entrada_selecionada:
                    entrada_id = id_entrada
                    break
            
            if not entrada_id:
                entrada_id = "default"
            
            # Construir comando pw-record
            cmd = ["pw-record", "--rate", "48000", "--channels", "2"]
            
            # Adiciona target se não for default
            if entrada_id != "default":
                cmd.extend(["--target", entrada_id])
            
            cmd.append(self.arquivo_wav)
            
            # Inicia gravação
            self.processo = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            self.status.config(
                text=f"Status: gravando\n{os.path.basename(self.arquivo_wav)}\nEntrada: {entrada_selecionada}",
                fg="green"
            )
            self.btn_gravar.config(state="disabled")
            self.btn_pausar.config(state="normal")
            self.btn_finalizar.config(state="normal")
            self.pausado = False

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao iniciar gravação:\n{str(e)}")

    def pausar(self):
        if not self.processo:
            return

        if not self.pausado:
            try:
                os.kill(self.processo.pid, signal.SIGSTOP)
                self.status.config(text="Status: pausado", fg="orange")
                self.btn_pausar.config(text="▶️ Continuar")
                self.pausado = True
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao pausar: {str(e)}")
        else:
            try:
                os.kill(self.processo.pid, signal.SIGCONT)
                self.status.config(text="Status: gravando", fg="green")
                self.btn_pausar.config(text="⏸️ Pausar")
                self.pausado = False
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao continuar: {str(e)}")

    def finalizar(self):
        if self.processo:
            self.processo.terminate()
            try:
                stdout, stderr = self.processo.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                self.processo.kill()
                stdout, stderr = self.processo.communicate()

        # Valida se arquivo WAV foi criado
        if not os.path.exists(self.arquivo_wav):
            messagebox.showerror(
                "Erro",
                f"Arquivo WAV não foi criado:\n{self.arquivo_wav}\n\n"
                f"Verifique se a entrada de áudio está funcionando.\n\n"
                f"Teste com: pw-record --rate 48000 --channels 2 /tmp/teste.wav"
            )
            self.btn_gravar.config(state="normal")
            self.btn_pausar.config(state="disabled", text="⏸️ Pausar")
            self.btn_finalizar.config(state="disabled")
            self.processo = None
            self.pausado = False
            return

        try:
            # Converte para MP3 com melhor tratamento de erros
            resultado = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", self.arquivo_wav,
                    "-codec:a", "libmp3lame",
                    "-q:a", "2",
                    self.arquivo_mp3
                ],
                capture_output=True,
                text=True,
                timeout=300
            )

            if resultado.returncode != 0:
                # Se ffmpeg retornar erro, tenta com alternativa
                mensagem_erro = resultado.stderr if resultado.stderr else resultado.stdout
                
                if "libmp3lame" in mensagem_erro.lower() or "codec" in mensagem_erro.lower():
                    # Tenta com aac (codec nativo disponível)
                    resultado = subprocess.run(
                        [
                            "ffmpeg", "-y",
                            "-i", self.arquivo_wav,
                            "-codec:a", "aac",
                            "-q:a", "5",
                            self.arquivo_mp3.replace(".mp3", ".m4a")
                        ],
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    
                    if resultado.returncode == 0:
                        os.rename(
                            self.arquivo_mp3.replace(".mp3", ".m4a"),
                            self.arquivo_mp3
                        )
                        messagebox.showwarning(
                            "Conversão com AAC",
                            "ffmpeg não tem libmp3lame. Convertido com codec AAC em vez de MP3."
                        )
                    else:
                        raise Exception(f"Erro ffmpeg (AAC): {resultado.stderr}")
                else:
                    raise Exception(f"Erro ffmpeg:\n{mensagem_erro}")

            if os.path.exists(self.arquivo_wav):
                os.remove(self.arquivo_wav)

            self.status.config(
                text=f"Status: conversão concluída ✓",
                fg="blue"
            )

            # Inicia transcrição automática em thread separada se ativada
            if self.transcricao_var.get():
                self.status.config(
                    text=f"Status: iniciando transcrição...\n⏳ Aguarde (pode levar alguns minutos)",
                    fg="orange"
                )
                self.root.update()  # Atualiza a interface
                
                self.transcrevendo = True
                self.thread_transcricao = threading.Thread(
                    target=self.transcrever,
                    args=(self.arquivo_mp3,),
                    daemon=False
                )
                self.thread_transcricao.start()

        except subprocess.TimeoutExpired:
            messagebox.showerror("Erro", "Conversão para MP3 expirou (timeout > 5 minutos)")
        except Exception as e:
            messagebox.showerror("Erro ao converter MP3", f"{str(e)}\n\nVerifique se ffmpeg está instalado:\nsudo apt install ffmpeg libmp3lame0")

        self.btn_gravar.config(state="normal")
        self.btn_pausar.config(state="disabled", text="⏸️ Pausar")
        self.btn_finalizar.config(state="disabled")

        self.processo = None
        self.pausado = False

    def selecionar_pasta(self):
        pasta = filedialog.askdirectory(initialdir=self.pasta_selecionada, title="Selecione a pasta para salvar")
        if pasta:
            # Valida se a pasta tem permissão de escrita
            try:
                teste_arquivo = os.path.join(pasta, ".gravador_teste")
                with open(teste_arquivo, "w") as f:
                    f.write("")
                os.remove(teste_arquivo)
                self.pasta_selecionada = pasta
                self.label_pasta.config(text=self.pasta_selecionada)
            except PermissionError:
                messagebox.showerror("Erro", f"Sem permissão de escrita em: {pasta}")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao acessar pasta: {str(e)}")

    def transcrever(self, arquivo_audio):
        """Transcreve `arquivo_audio` usando a biblioteca `whisper`.
        Salva o texto em um arquivo .txt ao lado do arquivo de áudio com o mesmo nome.
        Executa em thread separada para não congelar a interface.
        """
        try:
            # Verifica se whisper está instalado
            import whisper
            
            # Atualizar interface (thread-safe)
            self.root.after(0, lambda: self.status.config(
                text=f"Status: carregando modelo Whisper...\n⏳ Aguarde",
                fg="orange"
            ))
            
            # Carrega modelo (pequeno = ~141MB, ~10-30s para carregar)
            try:
                model = whisper.load_model("small", device="cpu")
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "Erro ao carregar Whisper",
                    f"Erro ao carregar modelo: {str(e)}\n\nTente novamente ou reinstale: pip install -U openai-whisper"
                ))
                self.transcrevendo = False
                return
            
            # Atualizar interface
            self.root.after(0, lambda: self.status.config(
                text=f"Status: transcrevendo áudio...\n⏳ Aguarde (pode levar 1-5 minutos)",
                fg="orange"
            ))
            
            # Realiza a transcrição
            result = model.transcribe(arquivo_audio, verbose=False)
            texto = result.get("text", "").strip()
            
            # Quebra de linha após cada ponto
            texto = re.sub(r"\.\s+", ".\n", texto).strip()
            
            if texto:
                # Salva arquivo de transcrição
                txt_path = os.path.splitext(arquivo_audio)[0] + ".txt"
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(texto)
                
                # Atualizar interface (thread-safe)
                self.root.after(0, lambda: self.atualizar_status_transcricao_ok(txt_path))
            else:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Transcrição",
                    "Nenhum texto detectado na gravação.\nVerifique a qualidade do áudio."
                ))
                self.root.after(0, lambda: self.status.config(
                    text=f"Status: finalizado ✓\n{arquivo_audio}",
                    fg="blue"
                ))
        
        except ImportError:
            self.root.after(0, lambda: messagebox.showinfo(
                "Whisper não instalado",
                "Para usar transcrição automática, instale:\n\n    pip install -U openai-whisper\n\nPara GPU (CUDA):\n    pip install -U openai-whisper\n    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118"
            ))
            self.root.after(0, lambda: self.status.config(
                text=f"Status: finalizado ✓\n{arquivo_audio}",
                fg="blue"
            ))
        
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(
                "Erro na transcrição",
                f"Erro ao transcrever: {str(e)}\n\nVerifique os requisitos:\ninstall -U openai-whisper"
            ))
            self.root.after(0, lambda: self.status.config(
                text=f"Status: finalizado ✓\n{arquivo_audio}",
                fg="blue"
            ))
        
        finally:
            self.transcrevendo = False
    
    def atualizar_status_transcricao_ok(self, txt_path):
        """Atualiza interface após sucesso na transcrição (thread-safe)."""
        self.status.config(
            text=f"Status: transcrição concluída ✓\n{txt_path}",
            fg="green"
        )
        messagebox.showinfo(
            "Transcrição concluída",
            f"Texto salvo em:\n{txt_path}"
        )


# ---- Execução ----
if __name__ == "__main__":
    root = tk.Tk()
    app = GravadorApp(root)
    root.mainloop()
