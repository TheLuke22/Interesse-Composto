import os
import streamlit as st
import logging

logger = logging.getLogger("MonetizationEngine")

# Password Segreta Admin (modificabile o tramite variabile d'ambiente)
ADMIN_SECRET_KEY = os.environ.get("ADMIN_SECRET_KEY", "admin2026")

# Configura le tue chiavi Stripe (o imposta variabili d'ambiente)
STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY", "pk_test_sample_key")
STRIPE_PAYMENT_LINK_MONTHLY = os.environ.get("STRIPE_LINK_MONTHLY", "https://buy.stripe.com/test_monthly_pro")
STRIPE_PAYMENT_LINK_ANNUAL = os.environ.get("STRIPE_LINK_ANNUAL", "https://buy.stripe.com/test_annual_pro")

# Links Affiliazione Broker (High CPA)
BROKER_AFFILIATE_LINKS = {
    "Interactive Brokers": "https://www.interactivebrokers.com/mkt/?src=business_segments",
    "Trade Republic": "https://traderepublic.com/referral?code=business_segments",
    "eToro": "https://med.etoro.com/B1234_A5678_TClick.aspx",
    "Freedom24": "https://freedom24.com/?utm_source=business_segments"
}

def check_is_admin() -> bool:
    """
    Verifica se l'utente corrente è l'Admin/Creatore.
    Riconosce l'admin tramite:
    1. Parametro URL Segreto: ?admin=1 oppure ?key=admin2026
    2. Session state 'is_admin_authenticated' = True
    """
    if "is_admin_authenticated" not in st.session_state:
        st.session_state["is_admin_authenticated"] = False
        
    # Check URL Parameters (es. il tuo-sito.streamlit.app/?admin=1)
    try:
        qp = st.query_params
        if qp.get("admin") == "1" or qp.get("key") == ADMIN_SECRET_KEY:
            st.session_state["is_admin_authenticated"] = True
    except Exception:
        pass
        
    return st.session_state["is_admin_authenticated"]


def is_user_pro() -> bool:
    """Verifica se l'utente corrente ha attivo il piano PRO (oppure è Admin)."""
    if check_is_admin():
        return True
    if "is_pro_user" not in st.session_state:
        st.session_state["is_pro_user"] = False
    return st.session_state["is_pro_user"]


def render_admin_login_sidebar():
    """Renderizza il box discreto di accesso Admin nella barra laterale per il creatore."""
    is_admin = check_is_admin()
    
    with st.sidebar.expander("🔐 Accesso Creatore / Admin", expanded=False):
        if is_admin:
            st.success("👑 Autenticato come Admin / Creatore")
            st.caption("Hai accesso illimitato Pro a tutti i ticker e strumenti.")
            if st.button("Esci da Admin Mode", key="logout_admin_btn"):
                st.session_state["is_admin_authenticated"] = False
                st.session_state["is_pro_user"] = False
                st.rerun()
        else:
            admin_input = st.text_input("Master Key Passcode:", type="password", key="admin_master_key_input", placeholder="Inserisci chiave segreta...")
            if st.button("Accedi come Admin", key="login_admin_btn"):
                if admin_input == ADMIN_SECRET_KEY:
                    st.session_state["is_admin_authenticated"] = True
                    st.session_state["is_pro_user"] = True
                    st.success("Accesso Admin Verificato!")
                    st.rerun()
                else:
                    st.error("Chiave errata.")


def render_paywall_modal(feature_name="Feature Pro"):
    """Renderizza un card/modal Glassmorphism per la conversione all'abbonamento PRO."""
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.98) 0%, rgba(30, 58, 138, 0.6) 100%); border: 2px solid rgba(0, 242, 254, 0.4); border-radius: 20px; padding: 28px; margin: 24px 0; box-shadow: 0 15px 40px rgba(0,242,254,0.15); text-align: center;">
        <span class="ticker-badge" style="font-size: 12px; padding: 4px 12px; background: linear-gradient(135deg, #EC4899 0%, #8B5CF6 100%);">🔒 Contenuto Pro Riservato</span>
        <h3 style="color: #FFFFFF; font-family: 'Outfit', sans-serif; font-size: 24px; font-weight: 800; margin: 12px 0 6px 0;">Sblocca l'accesso a Business Segments Pro</h3>
        <p style="color: #94A3B8; font-size: 14px; max-width: 600px; margin: 0 auto 20px auto;">
            La funzione <b>{feature_name}</b> (ricerca ticker illimitata, storico 2010-2026, breakdown trimestrali Q1-Q4 ed export CSV) è riservata agli abbonati Pro.
        </p>

        <div style="display: flex; justify-content: center; gap: 16px; flex-wrap: wrap; margin-bottom: 20px;">
            <div style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 14px; padding: 16px 24px; min-width: 200px;">
                <div style="color: #8A929A; font-size: 12px; font-weight: 700; text-transform: uppercase;">Piano Mensile</div>
                <div style="color: #00F2FE; font-size: 28px; font-weight: 800; margin: 4px 0;">€4,99 <span style="font-size: 14px; color: #94A3B8;">/mese</span></div>
                <a href="{STRIPE_PAYMENT_LINK_MONTHLY}" target="_blank" style="text-decoration: none;">
                    <div style="background: linear-gradient(90deg, #00F2FE 0%, #4FACFE 100%); color: #0F172A; font-weight: 800; padding: 10px 18px; border-radius: 10px; font-size: 13px; margin-top: 8px; box-shadow: 0 0 15px rgba(0,242,254,0.4);">
                        Abbonati a €4,99 (Stripe)
                    </div>
                </a>
            </div>
            
            <div style="background: rgba(0,255,127,0.05); border: 1px solid rgba(0,255,127,0.3); border-radius: 14px; padding: 16px 24px; min-width: 200px; position: relative;">
                <span style="position: absolute; top: -10px; right: 15px; background: #00FF7F; color: #0F172A; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 8px;">MIGLIOR VALORE</span>
                <div style="color: #8A929A; font-size: 12px; font-weight: 700; text-transform: uppercase;">Piano Annuale</div>
                <div style="color: #00FF7F; font-size: 28px; font-weight: 800; margin: 4px 0;">€49 <span style="font-size: 14px; color: #94A3B8;">/anno</span></div>
                <div style="color: #94A3B8; font-size: 11px; margin-bottom: 4px;">Equivale a soli <b>€4,08 / mese</b></div>
                <a href="{STRIPE_PAYMENT_LINK_ANNUAL}" target="_blank" style="text-decoration: none;">
                    <div style="background: linear-gradient(90deg, #00FF7F 0%, #10B981 100%); color: #0F172A; font-weight: 800; padding: 10px 18px; border-radius: 10px; font-size: 13px; margin-top: 8px; box-shadow: 0 0 15px rgba(0,255,127,0.4);">
                        Abbonati Annuale (Stripe)
                    </div>
                </a>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_broker_affiliate_card(ticker: str):
    """Renderizza banner di affiliazione con broker regolamentati (High CPA Commissions)."""
    st.markdown(f"""
    <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 20px; margin: 24px 0;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div>
                <span style="color: #00F2FE; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;">💰 Partnership Broker Ufficiali</span>
                <h4 style="color: #FFFFFF; font-family: 'Outfit', sans-serif; font-size: 16px; font-weight: 700; margin: 4px 0;">Vuoi investire o fare trading su {ticker}?</h4>
                <p style="color: #94A3B8; font-size: 13px; margin: 0;">Apri un conto di trading tramite le migliori piattaforme regolamentate a zero commissioni:</p>
            </div>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                <a href="{BROKER_AFFILIATE_LINKS['Interactive Brokers']}" target="_blank" style="text-decoration: none;">
                    <div style="background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.15); color: #FFFFFF; font-weight: 700; padding: 8px 14px; border-radius: 8px; font-size: 12px; transition: all 0.2s;">
                        🏛️ Interactive Brokers
                    </div>
                </a>
                <a href="{BROKER_AFFILIATE_LINKS['Trade Republic']}" target="_blank" style="text-decoration: none;">
                    <div style="background: rgba(0, 242, 254, 0.1); border: 1px solid rgba(0, 242, 254, 0.3); color: #00F2FE; font-weight: 700; padding: 8px 14px; border-radius: 8px; font-size: 12px;">
                        📱 Trade Republic
                    </div>
                </a>
                <a href="{BROKER_AFFILIATE_LINKS['eToro']}" target="_blank" style="text-decoration: none;">
                    <div style="background: rgba(0, 255, 127, 0.1); border: 1px solid rgba(0, 255, 127, 0.3); color: #00FF7F; font-weight: 700; padding: 8px 14px; border-radius: 8px; font-size: 12px;">
                        🌐 eToro
                    </div>
                </a>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
