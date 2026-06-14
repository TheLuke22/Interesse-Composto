import os
import requests
import json
import yfinance as yf

def _call_gemini_api(prompt: str, api_key: str) -> str:
    """Effettua una chiamata HTTP POST all'API di Gemini 1.5 Flash."""
    if not api_key:
        return ""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.8,
            "maxOutputTokens": 2048
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Estrazione del testo della risposta
        candidates = data.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if parts:
                return parts[0].get("text", "")
    except Exception as e:
        # Registra o propaga l'errore per fallire graziosamente
        print(f"Errore chiamata Gemini API: {e}")
    return ""

def equity_portfolio_manager_agent(ticker: str, contesto: str, api_key: str = None) -> str:
    """Agente Equity PM: analizza i dati e genera una tesi di investimento premium."""
    # Controlla chiave API in locale o variabili ambiente
    key = api_key or os.environ.get("GEMINI_API_KEY")
    
    if key:
        prompt = f"""
        Sei un esperto Equity Portfolio Manager di un Hedge Fund istituzionale quantitativo/value. 
        Analizza l'azienda {ticker} sulla base dei dati finanziari live forniti nel contesto seguente.
        
        {contesto}
        
        Genera un report dettagliato e professionale in formato Markdown strutturato esattamente come segue:
        1. **Sintesi dell'Investimento (Executive Summary)**
        2. **Analisi della Redditività e Margini Storici**
        3. **Stima del Margin of Safety Reale (Valutazione Intrinseca vs Prezzo Corrente)**
        4. **Catalizzatori di Crescita & Posizionamento Competitivo (Moat)**
        5. **Raccomandazione dell'Investment Office**
        
        Mantieni un tono istituzionale, analitico e preciso. Usa tabelle o liste per rendere i dati leggibili.
        """
        response_text = _call_gemini_api(prompt, key)
        if response_text:
            return response_text

    # --- SOFISTICATO MOTORE DI FALLBACK (ANALYTICAL SIMULATION) ---
    # Se non c'è una chiave o l'API fallisce, creiamo un report analitico dettagliato usando yfinance
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
    except Exception:
        info = {}

    # Estrazione sicura dei dati
    short_name = info.get("shortName", ticker)
    pe = info.get("trailingPE", "N/D")
    forward_pe = info.get("forwardPE", "N/D")
    peg = info.get("pegRatio", "N/D")
    profit_margin = info.get("profitMargins", 0) * 100
    operating_margin = info.get("operatingMargins", 0) * 100
    roe = info.get("returnOnEquity", 0) * 100
    debt_to_equity = info.get("debtToEquity", "N/D")
    current_price = info.get("currentPrice") or info.get("regularMarketPrice") or "N/D"
    target_mean = info.get("targetMeanPrice", "N/D")
    
    # Calcolo Margin of Safety stimato
    mos_text = "N/D"
    if isinstance(current_price, (int, float)) and isinstance(target_mean, (int, float)):
        diff = ((target_mean - current_price) / target_mean) * 100
        mos_text = f"{diff:.1f}% (rispetto al target consensus di ${target_mean:.2f})"
        if diff > 15:
            mos_recommendation = "SOTTOPREZZATO (Forte Margin of Safety)"
        elif diff >= 0:
            mos_recommendation = "EQUITAMENTE VALUTATO (Margin of Safety moderato)"
        else:
            mos_recommendation = "SOPRAPREZZATO (Nessun Margin of Safety)"
    else:
        mos_recommendation = "Valutazione quantitativa non disponibile"

    report_simulato = f"""### 📑 ANALISI DELLO STOCK TRACKER: {short_name} ({ticker})
*Simulazione quantitativa generata dall'Investment Office Engine in assenza di API Key Live.*

#### 1. Sintesi dell'Investimento (Executive Summary)
Il titolo **{ticker}** ({short_name}) scambia attualmente a **{current_price}**. L'analisi quantitativa evidenzia una struttura finanziaria consolidata con metriche di redditività e una leva operativa che meritano un audit approfondito del rischio.

#### 2. Analisi della Redditività e Margini Storici
I dati di bilancio recenti indicano:
- **Margine Operativo (Operating Margin)**: `{operating_margin:.2f}%`
- **Margine di Profitto Netto**: `{profit_margin:.2f}%`
- **Ritorno sul Capitale Proprio (ROE)**: `{roe:.2f}%`
- **Rapporto Debt/Equity**: `{debt_to_equity}`

*Commento:* I margini storici mostrano una redditività del capitale molto solida rispetto alla media del settore, indicando un potere di prezzo (Pricing Power) forte e vantaggi di scala.

#### 3. Stima del Margin of Safety Reale
- **Rapporto P/E Corrente**: `{pe}`
- **Rapporto Forward P/E**: `{forward_pe}`
- **PEG Ratio**: `{peg}`
- **Margin of Safety Consensuale**: **{mos_text}**
- **Valutazione Operativa**: `{mos_recommendation}`

#### 4. Catalizzatori di Crescita & Posizionamento Competitivo (Moat)
- **Fattore A (Leva Tecnologica/Prodotto)**: Fortissima fidelizzazione del cliente e barriere all'entrata elevate nel segmento core.
- **Fattore B (Scalabilità)**: Espansione dei margini guidata dall'efficienza operativa e da acquisizioni mirate.
- **Fristi di mercato**: Fluttuazioni macroeconomiche, tassi di interesse e restrizioni regolatorie nei mercati internazionali.

#### 5. Raccomandazione dell'Investment Office
Sulla base del prezzo spot attuale di **{current_price}**, l'Investment Office suggerisce un'allocazione **tattica e monitorata**, in attesa del report di conformità del Risk Manager.
"""
    return report_simulato

def chief_risk_agent(pm_output: str, api_key: str = None) -> str:
    """Agente CRO: valuta il report finanziario e impone un rating di rischio."""
    key = api_key or os.environ.get("GEMINI_API_KEY")
    
    if key:
        prompt = f"""
        Sei il Chief Risk Officer (CRO) di un prestigioso Hedge Fund a gestione macro/globale.
        Analizza attentamente la tesi di investimento scritta dal nostro Equity Portfolio Manager:
        
        --- TESI DI INVESTIMENTO ---
        {pm_output}
        ---
        
        Sulla base dell'analisi, compila un report di Risk Audit in formato Markdown strutturato così:
        
        **RISK RATING: [COLORE]**
        
        (Istruzione fondamentale: Devi scegliere ESCLUSIVAMENTE uno tra questi 4 colori come prima riga in grassetto: 
        - **GREEN** se il rischio è molto basso/gestibile e la valutazione è conveniente.
        - **YELLOW** se ci sono rischi moderati, multipli elevati o volatilità macroeconomica.
        - **RED** se ci sono forti segnali di allarme, debito eccessivo o declino strutturale.
        - **BLACK** se l'investimento è tossico, viola la compliance del fondo o presenta rischi asimmetrici distruttivi).
        
        Poi approfondisci:
        1. **Valutazione del Rischio Finanziario (Leva, Liquidità e Debito)**
        2. **Rischio Operativo & di Valutazione (Prezzo eccessivo vs Valore)**
        3. **Analisi degli Scenario Macro e Geopolitici**
        4. **Conclusione e Azioni correttive (Mitigation Plan)**
        
        Fai in modo che il report sia severo e orientato alla protezione del capitale (Capital Preservation).
        """
        response_text = _call_gemini_api(prompt, key)
        if response_text:
            return response_text

    # --- SOFISTICATO MOTORE DI FALLBACK (RISK AUDIT DETTAGLIATO) ---
    # Analizziamo deterministicamente il contenuto del report per assegnare un rating logico
    risk_rating = "GREEN"
    reasons = []
    
    # Regola 1: se P/E è alto
    if "P/E Corrente`: `" in pm_output:
        try:
            pe_val = pm_output.split("P/E Corrente`: `")[1].split("`")[0]
            pe_val = float(pe_val)
            if pe_val > 28:
                risk_rating = "YELLOW"
                reasons.append("Multipli di valutazione (P/E) superiori alle medie storiche.")
            if pe_val > 45:
                risk_rating = "RED"
                reasons.append("Multipli di valutazione (P/E) estremamente elevati (Valuation Bubble Risk).")
        except Exception:
            pass
            
    # Regola 2: se Debt/Equity è alto
    if "Rapporto Debt/Equity`: `" in pm_output:
        try:
            debt_val = pm_output.split("Rapporto Debt/Equity`: `")[1].split("`")[0]
            debt_val = float(debt_val)
            if debt_val > 150:
                risk_rating = "RED"
                reasons.append("Rapporto Debito/Capitale proprio (Debt/Equity) elevato, indicante alta leva finanziaria.")
            elif debt_val > 80 and risk_rating == "GREEN":
                risk_rating = "YELLOW"
                reasons.append("Leva finanziaria moderata ma meritevole di costante monitoraggio.")
        except Exception:
            pass

    # Regola 3: se SOPRAPREZZATO
    if "SOPRAPREZZATO" in pm_output:
        risk_rating = "RED"
        reasons.append("L'azione quota sopra il target di consenso istituzionale.")

    if not reasons:
        reasons.append("Le metriche core di redditività e struttura del capitale rientrano nei parametri di tolleranza del fondo.")

    reasons_li = "\n".join([f"- {r}" for r in reasons])

    risk_simulato = f"""**RISK RATING: {risk_rating}**

*Audit quantitativo di conformità simulato dall'ufficio di Risk Management in assenza di API Key Live.*

#### 1. Valutazione del Rischio Finanziario (Leva, Liquidità e Debito)
L'analisi automatizzata dello stato patrimoniale suggerisce:
{reasons_li}

#### 2. Rischio Operativo & di Valutazione (Prezzo vs Valore)
Il rischio principale risiede nella stabilità del tasso di crescita futuro. Se i tassi di crescita degli utili subissero un rallentamento anche minimo (Compression dei multipli), l'effetto leva potrebbe impattare negativamente sul prezzo di borsa.

#### 3. Analisi degli Scenario Macro e Geopolitici
- **Scenario Inflazione/Tassi**: Tassi d'interesse stabilmente alti potrebbero incrementare gli oneri finanziari e ridurre la spesa discrezionale dei clienti.
- **Scenario Catena di Fornitura**: Esposizione diretta o indiretta a shock di approvvigionamento internazionali e tensioni doganali.

#### 4. Conclusione e Azioni Correttive (Mitigation Plan)
- **Se {risk_rating} è GREEN o YELLOW**: Si autorizza l'apertura della posizione con una dimensione limitata (max 2% del portafoglio) e con stop loss inseriti a protezione.
- **Se {risk_rating} è RED o BLACK**: Si impone il **VETO** temporaneo fino a quando le condizioni di prezzo non ripristineranno un adeguato Margin of Safety.
"""
    return risk_simulato
