import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import subprocess
import os
import signal
import re
import threading
import warnings
import time
import queue
import math
import random
import json
import urllib.request
import urllib.parse
import urllib.error

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Configuracao do Telegram (persistente)
# ---------------------------------------------------------------------------
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".gravador_config.json")


def carregar_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def salvar_config(config: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Cliente Telegram Bot API
# ---------------------------------------------------------------------------
class TelegramClient:
    API_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, token: str = "", chat_id: str = ""):
        self.token = token
        self.chat_id = chat_id

    def configurar(self, token: str, chat_id: str):
        self.token = token.strip()
        self.chat_id = chat_id.strip()

    def validar(self) -> tuple:
        if not self.token:
            return False, "Token da API nao configurado"
        if not self.chat_id:
            return False, "Chat ID nao configurado"
        try:
            url = self.API_URL.format(token=self.token, method="getMe")
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    bot_name = data["result"].get("username", "Bot")
                    return True, f"Conectado como @{bot_name}"
                return False, f"Erro da API: {data.get('description', 'desconhecido')}"
        except urllib.error.HTTPError as e:
            return False, f"Erro HTTP {e.code}: token invalido?"
        except Exception as e:
            return False, f"Erro de conexao: {str(e)}"

    def enviar_mensagem(self, texto: str) -> tuple:
        if not self.token or not self.chat_id:
            return False, "Nao configurado"
        try:
            url = self.API_URL.format(token=self.token, method="sendMessage")
            payload = {"chat_id": self.chat_id, "text": texto, "parse_mode": "HTML"}
            data = urllib.parse.urlencode(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("ok", False), result.get("description", "")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            try:
                err_json = json.loads(err_body)
                return False, f"HTTP {e.code}: {err_json.get('description', err_body[:100])}"
            except:
                return False, f"HTTP {e.code}: {err_body[:100]}"
        except Exception as e:
            return False, str(e)

    def enviar_arquivo(self, caminho_arquivo: str, caption: str = "", tipo: str = "document") -> tuple:
        if not self.token or not self.chat_id:
            return False, "Nao configurado"
        if not os.path.exists(caminho_arquivo):
            return False, f"Arquivo nao existe: {caminho_arquivo}"

        method = {"document": "sendDocument", "audio": "sendAudio", "voice": "sendVoice"}.get(tipo, "sendDocument")
        url = self.API_URL.format(token=self.token, method=method)

        try:
            boundary = "----GravadorBoundary" + str(int(time.time()))
            filename = os.path.basename(caminho_arquivo)
            mime_types = {
                ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav",
                ".txt": "text/plain", ".ogg": "audio/ogg"
            }
            ext = os.path.splitext(filename)[1].lower()
            mime = mime_types.get(ext, "application/octet-stream")

            parts = []
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(b'Content-Disposition: form-data; name="chat_id"\r\n\r\n')
            parts.append(f"{self.chat_id}\r\n".encode())

            if caption:
                parts.append(f"--{boundary}\r\n".encode())
                parts.append(b'Content-Disposition: form-data; name="caption"\r\n\r\n')
                parts.append(f"{caption}\r\n".encode())

            parts.append(f"--{boundary}\r\n".encode())
            parts.append(f'Content-Disposition: form-data; name="{tipo}"; filename="{filename}"\r\n'.encode())
            parts.append(f"Content-Type: {mime}\r\n\r\n".encode())

            with open(caminho_arquivo, "rb") as f:
                file_data = f.read()
            parts.append(file_data)
            parts.append(f"\r\n--{boundary}--\r\n".encode())

            body = b"".join(parts)
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
            req.add_header("Content-Length", str(len(body)))

            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("ok", False), result.get("description", "")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            try:
                err_json = json.loads(err_body)
                desc = err_json.get('description', '')
                if "Forbidden" in desc or "bot was blocked" in desc:
                    return False, f"Bot sem permissao. Inicie uma conversa com o bot no Telegram primeiro. ({desc})"
                elif "chat not found" in desc:
                    return False, f"Chat ID invalido. Verifique se iniciou conversa com o bot. ({desc})"
                return False, f"HTTP {e.code}: {desc}"
            except:
                return False, f"HTTP {e.code}: {err_body[:200]}"
        except Exception as e:
            return False, str(e)

    def enviar_audio_completo(self, mp3_path: str, txt_path: str, titulo: str, duracao: str) -> tuple:
        ok1, msg1 = self.enviar_arquivo(mp3_path, caption=f"<b>{titulo}</b>\nDuracao: {duracao}", tipo="audio")
        if not ok1:
            return False, msg1
        if os.path.exists(txt_path):
            ok2, msg2 = self.enviar_arquivo(txt_path, caption=f"Transcricao: {os.path.basename(mp3_path)}", tipo="document")
            if not ok2:
                return False, msg2
        return True, "Enviado com sucesso"


# ---------------------------------------------------------------------------
# Fila sequencial de transcricoes - UMA POR VEZ, nunca perde nenhuma
# ---------------------------------------------------------------------------
_transcricoes_ativas: dict = {}
_transcricoes_lock = threading.Lock()
_transcricao_fila: queue.Queue = queue.Queue()
_transcricao_thread = None
_transcricao_running = False


def _atualizar_status_transcricao(arquivo: str, status: str, progresso: float = 0.0, posicao: int = 0):
    with _transcricoes_lock:
        _transcricoes_ativas[arquivo] = {
            "status": status,
            "progresso": progresso,
            "posicao": posicao
        }


def _remover_transcricao(arquivo: str):
    with _transcricoes_lock:
        if arquivo in _transcricoes_ativas:
            del _transcricoes_ativas[arquivo]


def _worker_transcricao_sequencial(arquivo_audio: str, callback_status, callback_erro,
                                    telegram_client=None, enviar_telegram=False,
                                    titulo="", duracao="00:00"):
    try:
        import whisper
        _atualizar_status_transcricao(arquivo_audio, "carregando_modelo", 5.0, 0)
        callback_status(f"[Whisper] Carregando modelo para {os.path.basename(arquivo_audio)}...")

        model = whisper.load_model("small", device="cpu")
        _atualizar_status_transcricao(arquivo_audio, "transcrevendo", 30.0, 0)
        callback_status(f"[Whisper] Transcrevendo {os.path.basename(arquivo_audio)}...")

        result = model.transcribe(arquivo_audio, verbose=False)
        _atualizar_status_transcricao(arquivo_audio, "processando_texto", 80.0, 0)

        texto = result.get("text", "").strip()
        texto = re.sub(r"\.\s+", ".\n", texto).strip()

        _atualizar_status_transcricao(arquivo_audio, "salvando", 95.0, 0)
        txt_path = os.path.splitext(arquivo_audio)[0] + ".txt"
        if texto:
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(texto)
            _atualizar_status_transcricao(arquivo_audio, "concluido", 100.0, 0)
            callback_status(f"[Whisper] Concluido -> {os.path.basename(txt_path)}")
        else:
            _atualizar_status_transcricao(arquivo_audio, "concluido_vazio", 100.0, 0)
            callback_status(f"[Whisper] Nenhum texto detectado em {os.path.basename(arquivo_audio)}")

        # Envia para Telegram se configurado
        if enviar_telegram and telegram_client and telegram_client.token:
            _atualizar_status_transcricao(arquivo_audio, "enviando_telegram", 100.0, 0)
            callback_status(f"[Telegram] Enviando {os.path.basename(arquivo_audio)}...")
            ok, msg = telegram_client.enviar_audio_completo(
                arquivo_audio, txt_path, titulo or os.path.basename(arquivo_audio), duracao)
            if ok:
                callback_status(f"[Telegram] Enviado com sucesso: {os.path.basename(arquivo_audio)}")
            else:
                callback_erro(f"[Telegram] {msg}")

        time.sleep(0.5)
        _remover_transcricao(arquivo_audio)

    except ImportError:
        _remover_transcricao(arquivo_audio)
        callback_erro("Whisper nao instalado. Execute: pip install -U openai-whisper")
    except Exception as e:
        _remover_transcricao(arquivo_audio)
        callback_erro(f"Erro Whisper ({os.path.basename(arquivo_audio)}): {e}")


def _fila_transcricao_loop():
    global _transcricao_running
    _transcricao_running = True
    while _transcricao_running:
        try:
            item = _transcricao_fila.get(timeout=1.0)
            if item is None:
                continue
            arquivo_audio, callback_status, callback_erro, telegram_client, enviar_telegram, titulo, duracao = item
            _worker_transcricao_sequencial(arquivo_audio, callback_status, callback_erro,
                                            telegram_client, enviar_telegram, titulo, duracao)
            _transcricao_fila.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            pass


def enfileirar_transcricao(arquivo_audio: str, callback_status, callback_erro,
                            telegram_client=None, enviar_telegram=False,
                            titulo="", duracao="00:00"):
    global _transcricao_thread

    _atualizar_status_transcricao(arquivo_audio, "na_fila", 0.0, _transcricao_fila.qsize() + 1)
    callback_status(f"[Whisper] Enfileirado para transcricao: {os.path.basename(arquivo_audio)}")
    _transcricao_fila.put((arquivo_audio, callback_status, callback_erro, telegram_client, enviar_telegram, titulo, duracao))

    if _transcricao_thread is None or not _transcricao_thread.is_alive():
        _transcricao_thread = threading.Thread(target=_fila_transcricao_loop, daemon=True, name="TranscricaoWorker")
        _transcricao_thread.start()


def parar_fila_transcricao():
    global _transcricao_running, _transcricao_thread
    _transcricao_running = False
    if _transcricao_thread is not None and _transcricao_thread.is_alive():
        _transcricao_thread.join(timeout=2)


# ---------------------------------------------------------------------------
# Fila sequencial de POS-PROCESSAMENTO (conversao + transcricao + telegram)
# ---------------------------------------------------------------------------
class PostProcessQueue:
    """Fila sequencial para converter WAV->MP3, transcrever e enviar Telegram.
    Garante que cada arquivo seja totalmente processado antes do proximo."""
    
    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()
        self._processados = 0
    
    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._loop, daemon=True, name="PostProcessWorker")
            self._thread.start()
    
    def stop(self):
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
    
    def enqueue(self, item: dict):
        """Item deve conter: wav_path, mp3_path, titulo, duracao, 
        transcricao_var, telegram_var, telegram_client, log_callback, status_callback"""
        self._queue.put(item)
    
    def count(self) -> int:
        return self._queue.qsize()
    
    def processados(self) -> int:
        return self._processados
    
    def _loop(self):
        item = None
        while self._running:
            try:
                item = self._queue.get(timeout=1.0)
                if item is None:
                    self._queue.task_done()
                    continue
                self._processar_item(item)
                self._processados += 1
            except queue.Empty:
                continue
            except Exception as e:
                if item is not None and "log_callback" in item:
                    item["log_callback"](f"[ERRO FATAL Pos-Processamento] {e}")
            finally:
                if item is not None:
                    self._queue.task_done()
                    item = None
    
    def _processar_item(self, item: dict):
        wav = item["wav_path"]
        mp3 = item["mp3_path"]
        titulo = item.get("titulo", "")
        duracao = item.get("duracao", "00:00")
        transcricao = item.get("transcricao_var", False)
        enviar_tg = item.get("telegram_var", False)
        tg_client = item.get("telegram_client")
        log = item["log_callback"]
        status = item.get("status_callback")
        
        basename_wav = os.path.basename(wav)
        basename_mp3 = os.path.basename(mp3)
        
        # 1. Verificar WAV valido
        if not os.path.exists(wav) or os.path.getsize(wav) < 1024:
            log(f"[Pos-Proc] WAV muito pequeno ou inexistente, descartando: {basename_wav}")
            try:
                if os.path.exists(wav):
                    os.remove(wav)
            except:
                pass
            return
        
        # Verificar duracao com ffprobe
        try:
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", wav],
                               capture_output=True, text=True, timeout=5)
            if r.returncode != 0 or not r.stdout.strip():
                log(f"[Pos-Proc] WAV corrompido (ffprobe falhou), descartando: {basename_wav}")
                try:
                    os.remove(wav)
                except:
                    pass
                return
            dur_wav = float(r.stdout.strip())
            if dur_wav < 0.5:
                log(f"[Pos-Proc] WAV muito curto ({dur_wav:.1f}s), descartando: {basename_wav}")
                try:
                    os.remove(wav)
                except:
                    pass
                return
        except Exception as e:
            log(f"[Pos-Proc] Erro ao verificar WAV {basename_wav}: {e}")
            return
        
        # 2. Converter para MP3
        log(f"[Pos-Proc] Convertendo {basename_wav} -> MP3...")
        try:
            r = subprocess.run(["ffmpeg", "-y", "-i", wav, "-codec:a", "libmp3lame", "-q:a", "2", mp3],
                capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                # Fallback AAC
                mp3_aac = mp3.replace(".mp3", ".m4a")
                r2 = subprocess.run(["ffmpeg", "-y", "-i", wav, "-codec:a", "aac", "-q:a", "5", mp3_aac],
                    capture_output=True, text=True, timeout=300)
                if r2.returncode == 0 and os.path.exists(mp3_aac) and os.path.getsize(mp3_aac) > 1024:
                    os.rename(mp3_aac, mp3)
                    log(f"[Pos-Proc] Convertido com AAC (fallback): {basename_mp3}")
                else:
                    log(f"[Pos-Proc] ERRO: Falha na conversao de {basename_wav}")
                    try:
                        os.remove(wav)
                        if os.path.exists(mp3_aac):
                            os.remove(mp3_aac)
                    except:
                        pass
                    return
            else:
                log(f"[Pos-Proc] Convertido: {basename_mp3}")
        except Exception as e:
            log(f"[Pos-Proc] ERRO na conversao de {basename_wav}: {e}")
            return
        finally:
            # Sempre remove WAV apos tentativa de conversao
            try:
                if os.path.exists(wav):
                    os.remove(wav)
            except:
                pass
        
        # 3. Verificar MP3 gerado
        if not os.path.exists(mp3) or os.path.getsize(mp3) < 1024:
            log(f"[Pos-Proc] ERRO: MP3 nao gerado ou muito pequeno: {basename_mp3}")
            return
        
        # 4. Transcricao. Esta etapa e sincrona para manter a ordem completa:
        # o proximo audio so comeca depois de transcrever e enviar este item.
        if transcricao:
            log(f"[Pos-Proc] Iniciando transcricao: {basename_mp3}")
            _worker_transcricao_sequencial(
                mp3, log,
                lambda msg: log(f"[ERRO] {msg}"),
                tg_client, enviar_tg and tg_client and tg_client.token, titulo, duracao
            )
        elif enviar_tg and tg_client and tg_client.token:
            # Envia so o audio se nao for transcrever
            log(f"[Pos-Proc] Enviando audio para Telegram (sem transcricao): {basename_mp3}")
            ok, msg = tg_client.enviar_audio_completo(mp3, "", titulo or basename_mp3, duracao)
            if ok:
                log(f"[Telegram] Enviado: {basename_mp3}")
            else:
                log(f"[Telegram] ERRO: {msg}")


# ---------------------------------------------------------------------------
# Visualizador de ondas sonoras
# ---------------------------------------------------------------------------
class WaveformVisualizer(tk.Canvas):
    def __init__(self, parent, width=600, height=100, **kwargs):
        super().__init__(parent, width=width, height=height, bg="#0d1117",
                         highlightthickness=1, highlightbackground="#30363d", **kwargs)
        self.width = width
        self.height = height
        self.bars = 60
        self.bar_width = width // self.bars
        self.gap = 1
        self.bar_values = [0.0] * self.bars
        self.target_values = [0.0] * self.bars
        self.active = False
        self.mode = "idle"
        self._animation_id = None
        self._draw()

    def _draw(self):
        self.delete("all")
        center_y = self.height // 2
        for i in range(self.bars):
            val = self.bar_values[i]
            bar_h = max(2, int(val * (self.height - 10) / 2))
            x0 = i * (self.bar_width + self.gap) + self.gap
            y0 = center_y - bar_h
            x1 = x0 + self.bar_width - self.gap
            y1 = center_y + bar_h
            if self.mode == "recording":
                color = "#ff6b6b" if val > 0.7 else "#4ecdc4" if val > 0.4 else "#45b7d1"
            elif self.mode == "paused":
                color = "#f0a500"
            else:
                color = "#30363d"
            self.create_rectangle(x0, y0, x1, y1, fill=color, outline="")
        status_text = {"recording": "GRAVANDO", "paused": "PAUSADO", "idle": "Aguardando audio..."}.get(self.mode, "")
        self.create_text(self.width // 2, self.height - 12, text=status_text,
                        fill="white" if self.mode != "idle" else "#666", font=("Courier", 8, "bold"))

    def _update(self):
        if not self.active:
            return
        for i in range(self.bars):
            diff = self.target_values[i] - self.bar_values[i]
            self.bar_values[i] += diff * 0.15
        self._draw()
        self._animation_id = self.after(30, self._update)

    def start(self):
        self.active = True
        self._update()

    def stop(self):
        self.active = False
        if self._animation_id:
            self.after_cancel(self._animation_id)
            self._animation_id = None
        self.bar_values = [0.0] * self.bars
        self.target_values = [0.0] * self.bars
        self.mode = "idle"
        self._draw()

    def set_mode(self, mode):
        self.mode = mode
        if mode == "idle":
            self.target_values = [0.0] * self.bars

    def simulate_audio(self, intensity=1.0):
        for i in range(self.bars):
            wave = math.sin(time.time() * 3 + i * 0.3) * 0.3 + 0.5
            noise = random.uniform(-0.2, 0.2)
            self.target_values[i] = max(0.05, min(1.0, (wave + noise) * intensity))

    def set_idle_wave(self):
        for i in range(self.bars):
            self.target_values[i] = max(0.02, math.sin(time.time() * 2 + i * 0.2) * 0.08 + 0.1)


# ---------------------------------------------------------------------------
# Monitor MPRIS
# ---------------------------------------------------------------------------
class MPRISMonitor:
    POLL_INTERVAL = 0.8

    def __init__(self, on_play, on_pause, on_stop, on_track_change):
        self.on_play = on_play
        self.on_pause = on_pause
        self.on_stop = on_stop
        self.on_track_change = on_track_change
        self._running = False
        self._thread = None
        self._prev_states = {}
        self._prev_titles = {}

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="MPRISMonitor")
        self._thread.start()

    def stop(self):
        self._running = False

    def _listar_players(self):
        try:
            r = subprocess.run(["dbus-send", "--session", "--print-reply",
                 "--dest=org.freedesktop.DBus", "/org/freedesktop/DBus",
                 "org.freedesktop.DBus.ListNames"], capture_output=True, text=True, timeout=3)
            players = re.findall(r'"(org\.mpris\.MediaPlayer2\.[^"]+)"', r.stdout)
            return players
        except Exception:
            return []

    def _get_property(self, service: str, prop: str) -> str:
        try:
            r = subprocess.run(["dbus-send", "--session", "--print-reply",
                 f"--dest={service}", "/org/mpris/MediaPlayer2",
                 "org.freedesktop.DBus.Properties.Get",
                 "string:org.mpris.MediaPlayer2.Player", f"string:{prop}"],
                capture_output=True, text=True, timeout=3)
            return r.stdout
        except Exception:
            return ""

    def _parse_playback_status(self, raw: str) -> str:
        m = re.search(r'string\s+"(\w+)"', raw)
        return m.group(1) if m else "Unknown"

    def _parse_title(self, raw: str) -> str:
        m = re.search(r'xesam:title.*?string\s+"([^"]+)"', raw, re.DOTALL)
        if m:
            return m.group(1)
        lines = raw.splitlines()
        for i, line in enumerate(lines):
            if "xesam:title" in line and i + 1 < len(lines):
                m2 = re.search(r'"([^"]+)"', lines[i + 1])
                if m2:
                    return m2.group(1)
        return ""

    def _get_track_info(self, service: str) -> str:
        raw = self._get_property(service, "Metadata")
        title = self._parse_title(raw)
        m_artist = re.search(r'xesam:artist.*?string\s+"([^"]+)"', raw, re.DOTALL)
        artist = m_artist.group(1) if m_artist else ""
        if artist and title:
            return f"{artist} - {title}"
        return title or service.split(".")[-1]

    def _loop(self):
        while self._running:
            players = self._listar_players()
            for svc in list(self._prev_states.keys()):
                if svc not in players:
                    if self._prev_states.get(svc) in ("Playing", "Paused"):
                        self.on_stop(svc)
                    del self._prev_states[svc]
                    self._prev_titles.pop(svc, None)

            for svc in players:
                raw_status = self._get_property(svc, "PlaybackStatus")
                status = self._parse_playback_status(raw_status)
                prev = self._prev_states.get(svc, "Unknown")
                current_title = self._get_track_info(svc)
                prev_title = self._prev_titles.get(svc, "")

                if status == "Playing" and prev == "Playing" and current_title != prev_title and current_title and prev_title:
                    self.on_track_change(svc, prev_title, current_title)
                    self._prev_titles[svc] = current_title
                    continue

                if status == "Playing" and prev != "Playing":
                    self._prev_titles[svc] = current_title
                    self.on_play(svc, current_title)
                elif status == "Paused" and prev == "Playing":
                    self.on_pause(svc, current_title)
                elif status != "Playing" and prev == "Playing":
                    self.on_stop(svc)
                elif status == "Playing" and prev == "Paused":
                    self._prev_titles[svc] = current_title
                    self.on_play(svc, current_title)

                self._prev_states[svc] = status
            time.sleep(self.POLL_INTERVAL)


# ---------------------------------------------------------------------------
# Aplicativo principal
# ---------------------------------------------------------------------------
class GravadorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gravador PulseAudio + Auto-Captura MPRIS + Telegram v2.5")
        self.root.geometry("980x980")
        self.root.resizable(False, False)
        try:
            self.root.iconbitmap("Recorder.ico")
        except Exception:
            pass

        self.processo = None
        self.pausado = False
        self.arquivo_atual = None
        self.auto_ativo = False
        self.auto_gravando = False
        self.auto_pausado = False
        self.auto_player_atual = ""
        self.auto_arquivo_wav = ""
        self.auto_arquivo_mp3 = ""
        self.auto_titulo_atual = ""
        self.auto_titulo_anterior = ""
        self.auto_inicio_timestamp = 0
        self._duration_running = False
        self._sim_running = False

        # NOVO: Lock e fila de pos-processamento sequencial
        self._gravacao_lock = threading.Lock()
        self._finalizando = False
        self._pp_queue = PostProcessQueue()
        self._pp_queue.start()

        # Configuracao do Telegram
        self.config = carregar_config()
        self.telegram = TelegramClient(
            token=self.config.get("telegram_token", ""),
            chat_id=self.config.get("telegram_chat_id", "")
        )

        self.mpris_monitor = MPRISMonitor(
            on_play=self._mpris_on_play, on_pause=self._mpris_on_pause,
            on_stop=self._mpris_on_stop, on_track_change=self._mpris_on_track_change)

        self.pasta_selecionada = os.getcwd()
        self.obter_entradas()
        self._build_ui()
        self._iniciar_updater_transcricao()

    def _build_ui(self):
        root = self.root
        tab_bar = tk.Frame(root, bg="#dde")
        tab_bar.pack(fill="x")
        self.frame_manual = tk.Frame(root)
        self.frame_auto = tk.Frame(root)
        self.frame_config = tk.Frame(root)

        def show_manual():
            self.frame_auto.pack_forget()
            self.frame_config.pack_forget()
            self.frame_manual.pack(fill="both", expand=True)
            btn_manual.config(relief="sunken")
            btn_auto.config(relief="raised")
            btn_config.config(relief="raised")
        def show_auto():
            self.frame_manual.pack_forget()
            self.frame_config.pack_forget()
            self.frame_auto.pack(fill="both", expand=True)
            btn_auto.config(relief="sunken")
            btn_manual.config(relief="raised")
            btn_config.config(relief="raised")
        def show_config():
            self.frame_manual.pack_forget()
            self.frame_auto.pack_forget()
            self.frame_config.pack(fill="both", expand=True)
            btn_config.config(relief="sunken")
            btn_manual.config(relief="raised")
            btn_auto.config(relief="raised")

        btn_manual = tk.Button(tab_bar, text="  Gravacao Manual  ", command=show_manual)
        btn_manual.pack(side="left", padx=2, pady=2)
        btn_auto = tk.Button(tab_bar, text="  Auto-Captura MPRIS  ", command=show_auto)
        btn_auto.pack(side="left", padx=2, pady=2)
        btn_config = tk.Button(tab_bar, text="  Configuracoes  ", command=show_config)
        btn_config.pack(side="left", padx=2, pady=2)

        self._build_tab_manual(self.frame_manual)
        self._build_tab_auto(self.frame_auto)
        self._build_tab_config(self.frame_config)
        show_manual()

        # === PAINEL DE FILA DE TRANSCRICAO ===
        transc_frame = tk.LabelFrame(root, text="Fila de Transcricoes", padx=8, pady=6)
        transc_frame.pack(fill="x", padx=10, pady=(4, 2))

        prog_frame = tk.Frame(transc_frame)
        prog_frame.pack(fill="x", pady=(0, 4))
        tk.Label(prog_frame, text="Atual:", font=("Helvetica", 9, "bold"), width=6, anchor="w").pack(side="left")
        self.transc_progress = ttk.Progressbar(prog_frame, orient="horizontal",
                                                mode="determinate", length=500, maximum=100)
        self.transc_progress.pack(side="left", padx=(4, 10))
        self.transc_label = tk.Label(prog_frame, text="Nenhuma transcricao em andamento",
                                      fg="#666", font=("Helvetica", 9), anchor="w")
        self.transc_label.pack(side="left", fill="x", expand=True)

        fila_frame = tk.Frame(transc_frame)
        fila_frame.pack(fill="x", pady=(2, 0))
        tk.Label(fila_frame, text="Na fila:", font=("Helvetica", 9, "bold"), width=6, anchor="w").pack(side="left")
        self.transc_fila_label = tk.Label(fila_frame, text="0 arquivo(s)", fg="#666", font=("Helvetica", 9))
        self.transc_fila_label.pack(side="left", padx=(4, 10))
        tk.Label(fila_frame, text="Processados:", font=("Helvetica", 9, "bold")).pack(side="left")
        self.transc_processados_label = tk.Label(fila_frame, text="0", fg="#666", font=("Helvetica", 9))
        self.transc_processados_label.pack(side="left", padx=(4, 0))

        list_frame = tk.Frame(transc_frame)
        list_frame.pack(fill="x", pady=(4, 0))
        tk.Label(list_frame, text="Status detalhado:", font=("Helvetica", 8), fg="#888").pack(anchor="w")
        self.transc_listbox = tk.Listbox(list_frame, height=4, width=100,
                                          font=("Courier", 8), fg="#333")
        self.transc_listbox.pack(fill="x")
        sb_list = tk.Scrollbar(list_frame, orient="horizontal", command=self.transc_listbox.xview)
        self.transc_listbox.config(xscrollcommand=sb_list.set)
        sb_list.pack(fill="x")

        tk.Label(root, text="Log:", anchor="w").pack(fill="x", padx=10)
        log_frame = tk.Frame(root)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.log_text = tk.Text(log_frame, height=6, state="disabled",
                                bg="#1e1e1e", fg="#ccffcc", font=("Courier", 9), wrap="word")
        sb = tk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _build_tab_manual(self, parent):
        tk.Label(parent, text="Nome do audio (sem extensao):").pack(pady=5)
        self.nome_audio = tk.Entry(parent, width=60)
        self.nome_audio.pack(pady=5)
        entrada_frame = tk.Frame(parent)
        entrada_frame.pack(pady=5, fill="x", padx=10)
        tk.Label(entrada_frame, text="Entrada de audio:").grid(row=0, column=0, sticky="w")
        self.entrada_var = tk.StringVar()
        self.entrada_opcoes = [f"{nome}" for nome, _ in self.entradas]
        if self.entrada_opcoes:
            self.entrada_var.set(self.entrada_opcoes[0])
        self.entrada_menu = tk.OptionMenu(entrada_frame, self.entrada_var, *self.entrada_opcoes)
        self.entrada_menu.grid(row=0, column=1, sticky="w", padx=(6, 10))
        tk.Button(entrada_frame, text="Atualizar", command=self.atualizar_entradas).grid(row=0, column=2, sticky="e", padx=(0, 10))

        pasta_frame = tk.Frame(parent)
        pasta_frame.pack(pady=5, fill="x", padx=10)
        tk.Label(pasta_frame, text="Salvar em:").grid(row=0, column=0, sticky="w")
        self.label_pasta = tk.Label(pasta_frame, text=self.pasta_selecionada, anchor="w", fg="gray")
        self.label_pasta.grid(row=0, column=1, sticky="w", padx=(6, 10))
        tk.Button(pasta_frame, text="Escolher pasta", command=self.selecionar_pasta).grid(row=0, column=2, sticky="e")

        self.status = tk.Label(parent, text="Status: parado", fg="blue")
        self.status.pack(pady=5)
        frame = tk.Frame(parent)
        frame.pack(pady=8)
        self.btn_gravar = tk.Button(frame, text="Gravar", width=12, command=self.gravar)
        self.btn_pausar = tk.Button(frame, text="Pausar", width=12, state="disabled", command=self.pausar)
        self.btn_finalizar = tk.Button(frame, text="Finalizar", width=12, state="disabled", command=self.finalizar)
        self.btn_gravar.grid(row=0, column=0, padx=5)
        self.btn_pausar.grid(row=0, column=1, padx=5)
        self.btn_finalizar.grid(row=0, column=2, padx=5)

        self.transcricao_var = tk.BooleanVar(value=True)
        tk.Checkbutton(frame, text="Transcrever apos gravar", variable=self.transcricao_var).grid(row=1, column=0, columnspan=3, pady=4)

        self.telegram_manual_var = tk.BooleanVar(value=self.config.get("enviar_telegram_manual", False))
        tk.Checkbutton(frame, text="Enviar para Telegram apos transcricao", variable=self.telegram_manual_var,
                       fg="#0088cc").grid(row=2, column=0, columnspan=3, pady=2)

    def _build_tab_auto(self, parent):
        desc = ("Monitoramento automatico via MPRIS (D-Bus).\n"
                "Compativel com Chromium, Firefox, VLC, Spotify e qualquer player KDE/MPRIS2.\n"
                "Play -> inicia gravacao  |  Pause -> pausa gravacao (retoma ao dar play)  |  Stop -> finaliza e transcreve\n"
                "Mudanca de faixa -> novo arquivo automaticamente")
        tk.Label(parent, text=desc, justify="left", fg="#444", wraplength=900).pack(padx=12, pady=8)

        wave_frame = tk.LabelFrame(parent, text="Visualizador de audio", padx=8, pady=8)
        wave_frame.pack(fill="x", padx=12, pady=4)
        self.waveform = WaveformVisualizer(wave_frame, width=900, height=100)
        self.waveform.pack()

        info_frame = tk.Frame(parent)
        info_frame.pack(fill="x", padx=12, pady=4)
        tk.Label(info_frame, text="Faixa atual:", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w")
        self.label_faixa_atual = tk.Label(info_frame, text="-", fg="#666", font=("Helvetica", 9))
        self.label_faixa_atual.grid(row=0, column=1, sticky="w", padx=6)
        tk.Label(info_frame, text="Arquivo:", font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w")
        self.label_arquivo_atual = tk.Label(info_frame, text="-", fg="#666", font=("Helvetica", 9))
        self.label_arquivo_atual.grid(row=1, column=1, sticky="w", padx=6)
        tk.Label(info_frame, text="Duracao:", font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w")
        self.label_duracao = tk.Label(info_frame, text="00:00", fg="#666", font=("Courier", 9))
        self.label_duracao.grid(row=2, column=1, sticky="w", padx=6)

        ent_frame = tk.Frame(parent)
        ent_frame.pack(fill="x", padx=12, pady=4)
        tk.Label(ent_frame, text="Entrada de audio (auto):").grid(row=0, column=0, sticky="w")
        self.auto_entrada_var = tk.StringVar()
        self.entrada_opcoes_auto = [f"{nome}" for nome, _ in self.entradas]
        if self.entrada_opcoes_auto:
            self.auto_entrada_var.set(self.entrada_opcoes_auto[0])
        self.auto_entrada_menu = tk.OptionMenu(ent_frame, self.auto_entrada_var, *self.entrada_opcoes_auto)
        self.auto_entrada_menu.grid(row=0, column=1, sticky="w", padx=(6, 10))

        pasta_frame2 = tk.Frame(parent)
        pasta_frame2.pack(fill="x", padx=12, pady=4)
        tk.Label(pasta_frame2, text="Salvar em:").grid(row=0, column=0, sticky="w")
        self.label_pasta_auto = tk.Label(pasta_frame2, text=self.pasta_selecionada, anchor="w", fg="gray")
        self.label_pasta_auto.grid(row=0, column=1, sticky="w", padx=(6, 10))
        tk.Button(pasta_frame2, text="Escolher pasta", command=self.selecionar_pasta).grid(row=0, column=2, sticky="e")

        detect_frame = tk.Frame(parent)
        detect_frame.pack(fill="x", padx=12, pady=4)
        tk.Label(detect_frame, text="Players MPRIS detectados:").grid(row=0, column=0, sticky="w")
        self.label_players = tk.Label(detect_frame, text="(nenhum)", fg="gray")
        self.label_players.grid(row=0, column=1, sticky="w", padx=6)
        tk.Button(detect_frame, text="Verificar agora", command=self._verificar_players).grid(row=0, column=2, padx=6)

        self.status_auto = tk.Label(parent, text="Auto-Captura: desativada", fg="gray")
        self.status_auto.pack(pady=6)

        ctrl = tk.Frame(parent)
        ctrl.pack(pady=4)
        self.btn_iniciar_auto = tk.Button(ctrl, text="Ativar Auto-Captura", width=22, bg="#2a7", fg="white", command=self.ativar_auto)
        self.btn_parar_auto = tk.Button(ctrl, text="Desativar", width=16, bg="#c44", fg="white", state="disabled", command=self.desativar_auto)
        self.btn_iniciar_auto.grid(row=0, column=0, padx=8)
        self.btn_parar_auto.grid(row=0, column=1, padx=8)

        self.transcricao_auto_var = tk.BooleanVar(value=True)
        tk.Checkbutton(ctrl, text="Transcrever automaticamente (Whisper)", variable=self.transcricao_auto_var).grid(row=1, column=0, columnspan=2, pady=4)

        self.telegram_auto_var = tk.BooleanVar(value=self.config.get("enviar_telegram_auto", False))
        tk.Checkbutton(ctrl, text="Enviar para Telegram apos transcricao", variable=self.telegram_auto_var,
                       fg="#0088cc").grid(row=2, column=0, columnspan=2, pady=2)

    def _build_tab_config(self, parent):
        tk.Label(parent, text="Configuracoes do Telegram Bot", font=("Helvetica", 12, "bold"), fg="#0088cc").pack(pady=10)

        info = ("1. Crie um bot no Telegram via @BotFather e copie o token\n"
                "2. Inicie uma conversa com o bot e obtenha seu Chat ID\n"
                "3. Use @userinfobot ou acesse: https://api.telegram.org/bot<TOKEN>/getUpdates")
        tk.Label(parent, text=info, justify="left", fg="#555", wraplength=800).pack(padx=20, pady=5)

        token_frame = tk.Frame(parent)
        token_frame.pack(fill="x", padx=20, pady=5)
        tk.Label(token_frame, text="Bot Token:", width=12, anchor="w").pack(side="left")
        self.entry_telegram_token = tk.Entry(token_frame, width=60, show="*")
        self.entry_telegram_token.pack(side="left", padx=(5, 0))
        self.entry_telegram_token.insert(0, self.config.get("telegram_token", ""))

        chat_frame = tk.Frame(parent)
        chat_frame.pack(fill="x", padx=20, pady=5)
        tk.Label(chat_frame, text="Chat ID:", width=12, anchor="w").pack(side="left")
        self.entry_telegram_chat = tk.Entry(chat_frame, width=30)
        self.entry_telegram_chat.pack(side="left", padx=(5, 0))
        self.entry_telegram_chat.insert(0, self.config.get("telegram_chat_id", ""))

        btn_testar = tk.Button(parent, text="Testar conexao", bg="#0088cc", fg="white",
                               command=self._testar_telegram)
        btn_testar.pack(pady=10)
        self.label_telegram_status = tk.Label(parent, text="Status: nao testado", fg="gray")
        self.label_telegram_status.pack()

        btn_salvar = tk.Button(parent, text="Salvar configuracoes", bg="#2a7", fg="white",
                               command=self._salvar_config_telegram)
        btn_salvar.pack(pady=10)

        tk.Label(parent, text="Dica: Para obter seu Chat ID, envie uma mensagem para o bot e acesse o link acima.",
                 fg="#888", font=("Helvetica", 8)).pack(pady=5)

    # -----------------------------------------------------------------------
    # Metodos Telegram
    # -----------------------------------------------------------------------
    def _testar_telegram(self):
        token = self.entry_telegram_token.get().strip()
        chat_id = self.entry_telegram_chat.get().strip()
        if not token:
            messagebox.showerror("Erro", "Informe o Bot Token")
            return
        if not chat_id:
            messagebox.showerror("Erro", "Informe o Chat ID")
            return

        temp_client = TelegramClient(token=token, chat_id=chat_id)
        self.label_telegram_status.config(text="Testando...", fg="orange")
        self.root.update()

        def _testar():
            ok, msg = temp_client.validar()
            self.root.after(0, lambda: self._atualizar_status_telegram(ok, msg))

        threading.Thread(target=_testar, daemon=True).start()

    def _atualizar_status_telegram(self, ok: bool, msg: str):
        if ok:
            self.label_telegram_status.config(text=f"Status: {msg}", fg="green")
            messagebox.showinfo("Sucesso", f"Conexao estabelecida!\n{msg}")
        else:
            self.label_telegram_status.config(text=f"Status: {msg}", fg="red")
            messagebox.showerror("Erro", f"Falha na conexao:\n{msg}")

    def _salvar_config_telegram(self):
        self.config["telegram_token"] = self.entry_telegram_token.get().strip()
        self.config["telegram_chat_id"] = self.entry_telegram_chat.get().strip()
        self.config["enviar_telegram_auto"] = self.telegram_auto_var.get()
        self.config["enviar_telegram_manual"] = self.telegram_manual_var.get()
        salvar_config(self.config)

        self.telegram.configurar(self.config["telegram_token"], self.config["telegram_chat_id"])
        messagebox.showinfo("Sucesso", "Configuracoes salvas!")
        self.log("Configuracoes do Telegram salvas.")

    # -----------------------------------------------------------------------
    # Updater de progresso de transcricao
    # -----------------------------------------------------------------------
    def _iniciar_updater_transcricao(self):
        self._transc_processados = 0
        def _loop():
            while True:
                try:
                    with _transcricoes_lock:
                        ativas = dict(_transcricoes_ativas)
                    fila_tamanho = _transcricao_fila.qsize()

                    if ativas:
                        arquivo, info = list(ativas.items())[-1]
                        progresso = info.get("progresso", 0)
                        status = info.get("status", "processando")
                        posicao = info.get("posicao", 0)

                        status_pt = {
                            "na_fila": f"Na fila (posicao {posicao})",
                            "carregando_modelo": "Carregando modelo Whisper...",
                            "transcrevendo": "Transcrevendo audio...",
                            "processando_texto": "Processando texto...",
                            "salvando": "Salvando arquivo...",
                            "enviando_telegram": "Enviando para Telegram...",
                            "concluido": "Transcricao concluida!",
                            "concluido_vazio": "Concluido (sem texto)"
                        }.get(status, status)

                        self.root.after(0, lambda p=progresso, s=status_pt, a=os.path.basename(arquivo), f=fila_tamanho:
                            self._atualizar_ui_transcricao(p, s, a, f))
                    else:
                        self.root.after(0, lambda f=fila_tamanho: self._limpar_ui_transcricao(f))
                except Exception:
                    pass
                time.sleep(0.5)
        threading.Thread(target=_loop, daemon=True).start()

    def _atualizar_ui_transcricao(self, progresso: float, status: str, arquivo: str, fila_tamanho: int):
        self.transc_progress["value"] = progresso
        self.transc_label.config(text=f"{status} ({progresso:.0f}%) - {arquivo}", fg="#333")
        self.transc_fila_label.config(text=f"{fila_tamanho} arquivo(s) na fila")

        self.transc_listbox.delete(0, tk.END)
        with _transcricoes_lock:
            for arq, info in _transcricoes_ativas.items():
                nome = os.path.basename(arq)
                prog = info.get("progresso", 0)
                st = info.get("status", "")
                pos = info.get("posicao", 0)
                if st == "na_fila":
                    linha = f"[FILA #{pos}] {nome[:50]:<50}"
                else:
                    linha = f"[PROC {prog:>5.0f}%] {nome[:50]:<50} {st}"
                self.transc_listbox.insert(tk.END, linha)

    def _limpar_ui_transcricao(self, fila_tamanho: int = 0):
        self.transc_progress["value"] = 0
        self.transc_label.config(text="Nenhuma transcricao em andamento", fg="#666")
        self.transc_fila_label.config(text=f"{fila_tamanho} arquivo(s) na fila")
        self.transc_listbox.delete(0, tk.END)

    # -----------------------------------------------------------------------
    # Log
    # -----------------------------------------------------------------------
    def log(self, msg: str):
        def _do():
            self.log_text.config(state="normal")
            self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.root.after(0, _do)

    # -----------------------------------------------------------------------
    # Atualizador de duracao
    # -----------------------------------------------------------------------
    def _start_duration_timer(self):
        self._duration_running = True
        def _tick():
            while self._duration_running:
                if self.auto_gravando and not self.auto_pausado:
                    elapsed = int(time.time() - self.auto_inicio_timestamp)
                    mins, secs = elapsed // 60, elapsed % 60
                    self.root.after(0, lambda m=mins, s=secs: self.label_duracao.config(text=f"{m:02d}:{s:02d}"))
                time.sleep(1)
        threading.Thread(target=_tick, daemon=True).start()

    def _stop_duration_timer(self):
        self._duration_running = False

    # -----------------------------------------------------------------------
    # MPRIS callbacks - CORRIGIDOS para respeitar lock de gravacao
    # -----------------------------------------------------------------------
    def _mpris_on_play(self, service: str, title: str):
        self.log(f"MPRIS Play detectado: {service} -> '{title}'")
        if not self.auto_ativo:
            return
        
        with self._gravacao_lock:
            # Se esta pausado e eh o mesmo player, retoma
            if self.auto_pausado and self.auto_player_atual == service and self.auto_gravando:
                self.root.after(0, lambda: self._auto_retomar_gravacao(service, title))
                return
            
            # Se ja esta gravando (ativo, nao pausado), finaliza a anterior primeiro
            if self.auto_gravando and not self.auto_pausado:
                self.log("Ja gravando - finalizando gravacao anterior antes de iniciar nova.")
                # Finaliza sincronamente o processo de gravacao
                self._finalizar_gravacao_sincrono()
                # Agenda nova gravacao apos liberar o lock
                self.root.after(100, lambda s=service, t=title: self._auto_iniciar_gravacao(s, t))
                return
            
            # Se nao esta gravando, inicia direto
            if not self.auto_gravando:
                self.root.after(0, lambda: self._auto_iniciar_gravacao(service, title))

    def _mpris_on_pause(self, service: str, title: str):
        self.log(f"MPRIS Pause detectado: {service} -> '{title}'")
        if not self.auto_ativo:
            return
        with self._gravacao_lock:
            if self.auto_gravando and self.auto_player_atual == service and not self.auto_pausado:
                self.root.after(0, lambda: self._auto_pausar_gravacao(service, title))

    def _mpris_on_stop(self, service: str):
        self.log(f"MPRIS Stop detectado: {service}")
        if not self.auto_ativo:
            return
        with self._gravacao_lock:
            if self.auto_gravando and self.auto_player_atual == service:
                self._finalizar_gravacao_sincrono()
            elif self.auto_pausado and self.auto_player_atual == service:
                self._finalizar_gravacao_sincrono()

    def _mpris_on_track_change(self, service: str, old_title: str, new_title: str):
        self.log(f"MPRIS Mudanca de faixa: '{old_title}' -> '{new_title}'")
        if not self.auto_ativo:
            return
        with self._gravacao_lock:
            if self.auto_gravando and self.auto_player_atual == service:
                self.log("Mudanca de faixa detectada - finalizando gravacao anterior.")
                self._finalizar_gravacao_sincrono()
                # Inicia nova gravacao apos pequeno delay para garantir que o arquivo foi fechado
                self.root.after(200, lambda s=service, t=new_title: self._auto_iniciar_gravacao(s, t))

    def _sanitizar_nome(self, nome: str) -> str:
        nome = re.sub(r'[\\/*?"<>|]', "_", nome)
        nome = nome.strip()[:80] or "gravacao_auto"
        return nome

    # -----------------------------------------------------------------------
    # Gravacao automatica - CORRIGIDA com lock e fila sequencial
    # -----------------------------------------------------------------------
    def _auto_iniciar_gravacao(self, service: str, title: str):
        with self._gravacao_lock:
            if self.auto_gravando:
                self.log("Tentativa de iniciar gravacao mas ja existe uma ativa. Ignorando.")
                return
            
            nome_arquivo = self._sanitizar_nome(title) + f"_{int(time.time())}"
            self.auto_arquivo_wav = os.path.join(self.pasta_selecionada, f"{nome_arquivo}.wav")
            self.auto_arquivo_mp3 = os.path.join(self.pasta_selecionada, f"{nome_arquivo}.mp3")
            self.auto_player_atual = service
            self.auto_titulo_atual = title
            self.auto_titulo_anterior = title
            self.auto_inicio_timestamp = time.time()
            self.auto_pausado = False
            self.auto_gravando = True

            entrada_selecionada = self.auto_entrada_var.get()
            entrada_id = self._resolver_entrada_id(entrada_selecionada)
            cmd = ["parecord", "--rate=48000", "--channels=2"]
            if entrada_id != "default":
                cmd.extend([f"--device={entrada_id}"])
            cmd.append(self.auto_arquivo_wav)

            try:
                self.auto_processo = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.status_auto.config(text=f"Gravando: {title[:60]}", fg="green")
                self.label_faixa_atual.config(text=title[:70], fg="green")
                self.label_arquivo_atual.config(text=os.path.basename(self.auto_arquivo_wav), fg="#333")
                self.waveform.set_mode("recording")
                self.waveform.start()
                self._start_simulating_audio()
                self._start_duration_timer()
                self.log(f"Gravacao iniciada -> {os.path.basename(self.auto_arquivo_wav)}")
            except Exception as e:
                self.log(f"ERRO ao iniciar gravacao automatica: {e}")
                self.auto_gravando = False
                self.auto_processo = None

    def _auto_pausar_gravacao(self, service: str, title: str):
        with self._gravacao_lock:
            if not self.auto_gravando or self.auto_pausado:
                return
            processo = getattr(self, "auto_processo", None)
            if processo:
                try:
                    os.kill(processo.pid, signal.SIGSTOP)
                    self.auto_pausado = True
                    self._elapsed_before_pause = time.time() - self.auto_inicio_timestamp
                    self.status_auto.config(text=f"Pausado: {title[:55]}", fg="orange")
                    self.label_faixa_atual.config(text=f"{title[:65]} (pausado)", fg="orange")
                    self.waveform.set_mode("paused")
                    self.log(f"Gravacao pausada -> {os.path.basename(self.auto_arquivo_wav)}")
                except Exception as e:
                    self.log(f"Erro ao pausar gravacao: {e}")

    def _auto_retomar_gravacao(self, service: str, title: str):
        with self._gravacao_lock:
            if not self.auto_gravando or not self.auto_pausado:
                return
            processo = getattr(self, "auto_processo", None)
            if processo:
                try:
                    os.kill(processo.pid, signal.SIGCONT)
                    self.auto_pausado = False
                    self.auto_inicio_timestamp = time.time() - getattr(self, '_elapsed_before_pause', 0)
                    self.status_auto.config(text=f"Gravando: {title[:60]}", fg="green")
                    self.label_faixa_atual.config(text=title[:70], fg="green")
                    self.waveform.set_mode("recording")
                    self.log(f"Gravacao retomada -> {os.path.basename(self.auto_arquivo_wav)}")
                except Exception as e:
                    self.log(f"Erro ao retomar gravacao: {e}")

    def _start_simulating_audio(self):
        self._sim_running = True
        def _sim():
            while self._sim_running:
                if self.auto_gravando and not self.auto_pausado:
                    self.waveform.simulate_audio(intensity=1.0)
                elif self.auto_pausado:
                    self.waveform.simulate_audio(intensity=0.15)
                else:
                    self.waveform.set_idle_wave()
                time.sleep(0.05)
        threading.Thread(target=_sim, daemon=True).start()

    def _stop_simulating_audio(self):
        self._sim_running = False

    def _finalizar_gravacao_sincrono(self):
        """Finaliza o processo de gravacao de forma sincrona e segura.
        Deve ser chamado DENTRO do _gravacao_lock."""
        if not self.auto_gravando:
            return
        
        self._stop_simulating_audio()
        self._stop_duration_timer()
        self.waveform.stop()

        processo = getattr(self, "auto_processo", None)
        wav = self.auto_arquivo_wav
        mp3 = self.auto_arquivo_mp3
        titulo = self.auto_titulo_atual
        duracao = self.label_duracao.cget("text")

        if processo:
            if self.auto_pausado:
                try:
                    os.kill(processo.pid, signal.SIGCONT)
                except:
                    pass
            processo.terminate()
            try:
                processo.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                processo.kill()
                processo.communicate()

        # Reset de estado
        self.auto_gravando = False
        self.auto_pausado = False
        self.auto_processo = None
        self.status_auto.config(text="Auto-Captura: aguardando reproducao...", fg="#555")
        self.label_faixa_atual.config(text="-", fg="#666")
        self.label_arquivo_atual.config(text="-", fg="#666")
        self.label_duracao.config(text="00:00")

        # Enfileira para pos-processamento sequencial (conversao + transcricao + telegram)
        if wav and os.path.exists(wav):
            self.log(f"Enfileirando pos-processamento: {os.path.basename(wav)}")
            self._pp_queue.enqueue({
                "wav_path": wav,
                "mp3_path": mp3,
                "titulo": titulo,
                "duracao": duracao,
                "transcricao_var": self.transcricao_auto_var.get(),
                "telegram_var": self.telegram_auto_var.get(),
                "telegram_client": self.telegram,
                "log_callback": self.log,
                "status_callback": None
            })
        else:
            self.log(f"AVISO: Arquivo WAV nao encontrado apos gravacao: {wav}")

    def _auto_finalizar_gravacao(self, iniciar_nova=None):
        """Metodo legacy - agora finalizacao eh sincrona via lock."""
        with self._gravacao_lock:
            self._finalizar_gravacao_sincrono()
        if iniciar_nova:
            self.root.after(200, lambda: self._auto_iniciar_gravacao(*iniciar_nova))

    # -----------------------------------------------------------------------
    # Botoes Auto-Captura
    # -----------------------------------------------------------------------
    def ativar_auto(self):
        if not self._verificar_dbus():
            messagebox.showerror("D-Bus indisponivel", "dbus-send nao encontrado.\nInstale: sudo apt install dbus")
            return
        self.auto_ativo = True
        self.mpris_monitor.start()
        self.status_auto.config(text="Auto-Captura: ativa - aguardando reproducao...", fg="#080")
        self.btn_iniciar_auto.config(state="disabled")
        self.btn_parar_auto.config(state="normal")
        self.log("Auto-Captura MPRIS ativada.")
        self._verificar_players()

    def desativar_auto(self):
        self.auto_ativo = False
        self.mpris_monitor.stop()
        with self._gravacao_lock:
            if self.auto_gravando:
                self._finalizar_gravacao_sincrono()
        self.status_auto.config(text="Auto-Captura: desativada", fg="gray")
        self.btn_iniciar_auto.config(state="normal")
        self.btn_parar_auto.config(state="disabled")
        self.log("Auto-Captura MPRIS desativada.")

    def _verificar_players(self):
        players = self.mpris_monitor._listar_players()
        if players:
            nomes = ", ".join(p.split(".")[-1] for p in players)
            self.label_players.config(text=nomes, fg="green")
            self.log(f"Players detectados: {nomes}")
        else:
            self.label_players.config(text="(nenhum)", fg="gray")
            self.log("Nenhum player MPRIS encontrado no momento.")

    # -----------------------------------------------------------------------
    # Utilitarios
    # -----------------------------------------------------------------------
    def _verificar_dbus(self) -> bool:
        try:
            subprocess.run(["dbus-send", "--version"], capture_output=True, timeout=2)
            return True
        except FileNotFoundError:
            return False

    def _resolver_entrada_id(self, nome_selecionado: str) -> str:
        for nome_entrada, id_entrada in self.entradas:
            if nome_entrada == nome_selecionado:
                return id_entrada
        return "default"

    # -----------------------------------------------------------------------
    # Gravacao Manual
    # -----------------------------------------------------------------------
    def obter_entradas(self):
        self.entradas = []
        try:
            resultado = subprocess.run(["pactl", "list", "short", "sources"],
                capture_output=True, text=True, timeout=5)
            if resultado.returncode == 0:
                for linha in resultado.stdout.strip().split('\n'):
                    if linha.strip():
                        partes = linha.split('\t')
                        if len(partes) >= 2:
                            self.entradas.append((partes[1].strip(), partes[0].strip()))
        except Exception:
            pass
        if not self.entradas:
            try:
                resultado = subprocess.run(["pactl", "info"], capture_output=True, text=True, timeout=5)
                if resultado.returncode == 0:
                    for linha in resultado.stdout.split('\n'):
                        if "Default Source" in linha:
                            nome = linha.split(':')[1].strip()
                            self.entradas.append((nome, "default"))
            except Exception:
                pass
        if not self.entradas:
            self.entradas = [("Entrada padrao", "default")]

    def atualizar_entradas(self):
        self.obter_entradas()
        for menu_var, menu_widget in [(self.entrada_var, self.entrada_menu), (self.auto_entrada_var, self.auto_entrada_menu)]:
            menu = menu_widget["menu"]
            menu.delete(0, "end")
            opcoes = [f"{nome}" for nome, _ in self.entradas]
            for opcao in opcoes:
                menu.add_command(label=opcao, command=lambda v=opcao, mv=menu_var: mv.set(v))
            if opcoes:
                menu_var.set(opcoes[0])
        messagebox.showinfo("Sucesso", f"{len(self.entradas)} entrada(s) de audio detectada(s).")

    def gravar(self):
        nome = self.nome_audio.get().strip()
        if not nome:
            messagebox.showerror("Erro", "Informe o nome do audio.")
            return
        entrada_selecionada = self.entrada_var.get()
        if not entrada_selecionada:
            messagebox.showerror("Erro", "Selecione uma entrada de audio.")
            return
        self.arquivo_wav = os.path.join(self.pasta_selecionada, f"{nome}.wav")
        self.arquivo_mp3 = os.path.join(self.pasta_selecionada, f"{nome}.mp3")
        if os.path.exists(self.arquivo_mp3):
            messagebox.showerror("Erro", "Esse arquivo ja existe na pasta selecionada.")
            return
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=2)
        except FileNotFoundError:
            messagebox.showerror("Erro", "ffmpeg nao esta instalado.\nInstale: sudo apt install ffmpeg libmp3lame0")
            return
        entrada_id = self._resolver_entrada_id(entrada_selecionada)
        cmd = ["parecord", "--rate=48000", "--channels=2"]
        if entrada_id != "default":
            cmd.extend([f"--device={entrada_id}"])
        cmd.append(self.arquivo_wav)
        try:
            self.processo = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.status.config(text=f"Status: gravando\n{os.path.basename(self.arquivo_wav)}\nEntrada: {entrada_selecionada}", fg="green")
            self.btn_gravar.config(state="disabled")
            self.btn_pausar.config(state="normal")
            self.btn_finalizar.config(state="normal")
            self.pausado = False
            self.log(f"Gravacao manual iniciada: {nome}")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao iniciar gravacao:\n{str(e)}")

    def pausar(self):
        if not self.processo:
            return
        if not self.pausado:
            try:
                os.kill(self.processo.pid, signal.SIGSTOP)
                self.status.config(text="Status: pausado", fg="orange")
                self.btn_pausar.config(text="Continuar")
                self.pausado = True
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao pausar: {str(e)}")
        else:
            try:
                os.kill(self.processo.pid, signal.SIGCONT)
                self.status.config(text="Status: gravando", fg="green")
                self.btn_pausar.config(text="Pausar")
                self.pausado = False
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao continuar: {str(e)}")

    def finalizar(self):
        if self.processo:
            self.processo.terminate()
            try:
                self.processo.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                self.processo.kill()
                self.processo.communicate()
        if not os.path.exists(self.arquivo_wav):
            messagebox.showerror("Erro", f"Arquivo WAV nao criado:\n{self.arquivo_wav}")
            self.btn_gravar.config(state="normal")
            self.btn_pausar.config(state="disabled", text="Pausar")
            self.btn_finalizar.config(state="disabled")
            self.processo = None
            self.pausado = False
            return

        # ===== CORRECAO: verificar WAV valido na gravacao manual tambem =====
        if not self._verificar_wav_valido(self.arquivo_wav):
            messagebox.showwarning("Aviso", "Gravacao muito curta ou corrompida. Arquivo descartado.")
            try:
                os.remove(self.arquivo_wav)
            except:
                pass
            self.btn_gravar.config(state="normal")
            self.btn_pausar.config(state="disabled", text="Pausar")
            self.btn_finalizar.config(state="disabled")
            self.processo = None
            self.pausado = False
            return

        try:
            r = subprocess.run(["ffmpeg", "-y", "-i", self.arquivo_wav, "-codec:a", "libmp3lame", "-q:a", "2", self.arquivo_mp3],
                capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                err = r.stderr or r.stdout
                if "libmp3lame" in err.lower() or "codec" in err.lower():
                    aac = self.arquivo_mp3.replace(".mp3", ".m4a")
                    subprocess.run(["ffmpeg", "-y", "-i", self.arquivo_wav, "-codec:a", "aac", "-q:a", "5", aac],
                        capture_output=True, text=True, timeout=300)
                    os.rename(aac, self.arquivo_mp3)
                    messagebox.showwarning("Conversao com AAC", "ffmpeg nao tem libmp3lame. Convertido com AAC.")
                else:
                    raise Exception(f"Erro ffmpeg:\n{err}")
            if os.path.exists(self.arquivo_wav):
                os.remove(self.arquivo_wav)

            # ===== CORRECAO: verificar MP3 gerado =====
            if not os.path.exists(self.arquivo_mp3) or os.path.getsize(self.arquivo_mp3) < 1024:
                messagebox.showerror("Erro", "MP3 nao foi gerado corretamente.")
                self.btn_gravar.config(state="normal")
                self.btn_pausar.config(state="disabled", text="Pausar")
                self.btn_finalizar.config(state="disabled")
                self.processo = None
                self.pausado = False
                return

            self.status.config(text="Conversao concluida", fg="blue")
            self.log(f"Gravacao manual finalizada: {os.path.basename(self.arquivo_mp3)}")
            if self.transcricao_var.get():
                mp3 = self.arquivo_mp3
                enviar_tg = self.telegram_manual_var.get() and self.telegram.token
                enfileirar_transcricao(mp3,
                    lambda msg: (self.log(msg), self.root.after(0, lambda m=msg: self.status.config(text=m, fg="orange"))),
                    lambda msg: self.log(f"[ERRO] {msg}"),
                    self.telegram, enviar_tg, os.path.basename(mp3), "00:00")
        except Exception as e:
            messagebox.showerror("Erro ao converter MP3", str(e))
        self.btn_gravar.config(state="normal")
        self.btn_pausar.config(state="disabled", text="Pausar")
        self.btn_finalizar.config(state="disabled")
        self.processo = None
        self.pausado = False

    def selecionar_pasta(self):
        pasta = filedialog.askdirectory(initialdir=self.pasta_selecionada, title="Selecione a pasta para salvar")
        if pasta:
            try:
                teste = os.path.join(pasta, ".gravador_teste")
                with open(teste, "w") as f:
                    f.write("")
                os.remove(teste)
                self.pasta_selecionada = pasta
                self.label_pasta.config(text=pasta)
                self.label_pasta_auto.config(text=pasta)
            except PermissionError:
                messagebox.showerror("Erro", f"Sem permissao de escrita em: {pasta}")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao acessar pasta: {str(e)}")

    def on_closing(self):
        self.mpris_monitor.stop()
        self._stop_simulating_audio()
        self._stop_duration_timer()
        if self.auto_gravando:
            self._auto_finalizar_gravacao()
        self._pp_queue.stop()
        parar_fila_transcricao()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = GravadorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
