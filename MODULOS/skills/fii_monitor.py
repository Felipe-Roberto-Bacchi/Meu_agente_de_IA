import time
import re
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

class FIIMonitor:
    def __init__(self, tickers: List[str]):
        """
        Módulo de Monitoramento de FIIs integrado.
        :param tickers: Lista contendo os códigos dos ativos. Ex: ["MXRF11", "XPML11"]
        """
        self.tickers = tickers
        # Headers forjados para simular um browser real e evitar HTTP 403 Forbidden 
        self.session_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive'
        }

    def _fetch_fundamentals(self, ticker: str) -> Optional[Dict[str, float]]:
        """
        Realiza o scraping no Fundamentus para extrair P/VP e Dividend Yield de forma estática (rápido).
        """
        url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker}"
        try:
            response = requests.get(url, headers=self.session_headers, timeout=8)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extração agressiva baseada em regex para evitar quebra caso o site sofra leves mutações no layout
            pvp_span = soup.find('span', string=re.compile(r'P/VP', re.IGNORECASE))
            pvp_value = 0.0
            if pvp_span:
                # O valor fica no próximo <td> referente ao <span> da label
                pvp_str = pvp_span.find_parent('td').find_next_sibling('td').text.strip()
                pvp_value = float(pvp_str.replace(',', '.'))

            dy_span = soup.find('span', string=re.compile(r'Div\. Yield', re.IGNORECASE))
            dy_value = 0.0
            if dy_span:
                dy_str = dy_span.find_parent('td').find_next_sibling('td').text.strip()
                dy_value = float(dy_str.replace('%', '').replace(',', '.'))

            return {'P/VP': pvp_value, 'DY': dy_value}
            
        except requests.exceptions.Timeout:
            print(f"[Aviso Jarvis] Timeout ao buscar fundamentos de {ticker}.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"[Aviso Jarvis] Falha de HTTP no scraping de {ticker}: {e}")
            return None
        except Exception as e:
            print(f"[Aviso Jarvis] Falha no parsing HTML de {ticker}: {e}")
            return None

    def _fetch_current_price(self, ticker: str) -> Optional[float]:
        """
        Realiza consulta do preço em base D0 operando via Yahoo Finance.
        """
        try:
            yf_ticker = yf.Ticker(f"{ticker}.SA")
            # Usa 'history' em vez de 'info' por ser muito menos sujeito a falhas em atualizações do yfinance.
            data = yf_ticker.history(period="1d", interval="1m")
            
            if not data.empty:
                return round(float(data['Close'].iloc[-1]), 2)
                
            # Fallback para o endpoint rápido do yfinance se a bolsa ainda não tiver volumes pro "history" atômico
            return round(float(yf_ticker.fast_info['lastPrice']), 2)
            
        except Exception as e:
            print(f"[Aviso Jarvis] Erro na requisição yfinance para {ticker}: {e}")
            return None

    def get_market_report(self) -> str:
        """
        Processa ativamente todos os indicadores em cache temporário.
        Processamento serial otimizado para o loop principal do TTS do LLM.
        """
        linhas_relatorio = ["Relatório de fundos imobiliários, senhor:"]
        
        for ticker in self.tickers:
            price = self._fetch_current_price(ticker)
            fundamentals = self._fetch_fundamentals(ticker)
            
            # Se algum falhou na rede, pula a iteração para não enviar "None" pro gerador de texto
            if price is None or fundamentals is None:
                print(f"[Aviso Jarvis] Pulando {ticker} devido a falha na coleta de dados.")
                continue

            pvp = fundamentals['P/VP']
            dy = fundamentals['DY']
            
            # Application Logic Requirement: OPORTUNIDADE ou AGUARDAR
            status = "oportunidade" if (pvp <= 1.05 and dy > 9.6) else "aguardar"
            
            # Formatação localizada e limpa para leitura por modelo de voz (Phonetic friendly)
            preco_str = f"{price:.2f}".replace('.', ',')
            pvp_str = f"{pvp:.2f}".replace('.', ',')
            dy_str = f"{dy:.1f}".replace('.', ',')
            
            linhas_relatorio.append(
                f"O fundo {ticker} está cotado em {preco_str} reais, "
                f"com preço sobre valor patrimonial de {pvp_str} e rendimento de {dy_str} por cento ao ano. "
                f"No momento, o status é de {status}."
            )
            
            # Delay de 1s pra não engatilhar blocos no server side da fundamentus
            time.sleep(1)

        if len(linhas_relatorio) == 1:
            return "Senhor, tive dificuldade em acessar os dados financeiros no momento. Por favor, tente novamente em instantes."

        return " ".join(linhas_relatorio)

# Ponto de acesso modular -> Chamar no arquivo de skills principal do seu assistente
def obter_resumo_fiis() -> str:
    ativos = ["MXRF11", "XPML11", "VGHF11", "BTLG11"]
    monitor = FIIMonitor(tickers=ativos)
    return monitor.get_market_report()

# Teste local da pipeline (Não roda se importado em outro arquivo)
if __name__ == "__main__":
    print("[Jarvis Debug Engine] Buscando métricas...\n")
    relatorio_para_tts = obter_resumo_fiis()
    print(relatorio_para_tts)
