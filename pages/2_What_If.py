import streamlit as st
import pandas as pd
import plotly.express as px
from fpl_engine import FPLMoneyLeague
from datetime import datetime

# Initialize
fpl = FPLMoneyLeague("126694")

st.set_page_config(page_title="What-If Machine", page_icon="🔮")
st.title("🔮 The What-If Machine")
st.markdown("Did your transfers actually help? Or should you have stayed in bed?")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Simulation Settings")    
    # 1. Fetch the list of managers
    # We use cache_data here so it doesn't hit the API every time you click a button
    @st.cache_data(ttl=3600)
    def fetch_managers():
        return fpl.get_league_managers()

    managers_dict = fetch_managers()
    
    if managers_dict:
        # Create the dropdown
        selected_name = st.selectbox(
            "Who are we analyzing?", 
            options=list(managers_dict.keys())
        )
        # Get the ID from the dictionary based on the name selected
        team_id = managers_dict[selected_name]
    else:
        # Fallback if the API fails or league is empty
        team_id = st.text_input("Enter Team ID manually", value="29690")

    st.divider()
    start_gw = st.number_input("Start Week", 1, 38, 1)
    
    current_gw_info = fpl._get_data("https://fantasy.premierleague.com/api/bootstrap-static/")
    current_gw = next(gw['id'] for gw in current_gw_info['events'] if gw['is_current'])
    
    end_gw = st.number_input("End Week", 1, 38, current_gw)
    deduct_hits = st.checkbox("Deduct Transfer Hits (-4)", value=True)

# --- CACHED CORE ---
@st.cache_data(show_spinner=False)
def run_simulation(team_id, start_gw, end_gw, deduct_hits):
    # 1. Get Set & Forget Squad (GW1)
    gw1_data = fpl._get_data(f"https://fantasy.premierleague.com/api/entry/{team_id}/event/{start_gw}/picks/")
    if not gw1_data: return None
    gw1_picks = gw1_data['picks']
    
    results = []
    sf_cum, actual_cum = 0, 0
    
    for gw in range(start_gw, end_gw + 1):
        live_stats = fpl.get_gw_live_data(gw)
        
        # Calculate Set & Forget Score
        sf_score = fpl.simulate_score(gw1_picks, live_stats)
        
        # Calculate Actual Score
        actual_data = fpl._get_data(f"https://fantasy.premierleague.com/api/entry/{team_id}/event/{gw}/picks/")
        actual_score = fpl.simulate_score(actual_data['picks'], live_stats)
        
        # Deduct hits if applicable
        if deduct_hits:
            hit_cost = actual_data.get('entry_history', {}).get('event_transfers_cost', 0)
            actual_score -= hit_cost
            
        sf_cum += sf_score
        actual_cum += actual_score
        
       # st.write(f"GW {gw}: Simulated {actual_score} vs Expected (Check FPL Site)")

        results.append({
            "GW": gw,
            "Set & Forget": sf_cum,
            "Actual Performance": actual_cum,
            "Difference": actual_cum - sf_cum
        })
    return results, sf_cum, actual_cum

# --- EXECUTION ---
if st.button("🚀 Run Analysis"):
    with st.spinner("Calculating alternate realities..."):
        sim_results = run_simulation(team_id, start_gw, end_gw, deduct_hits)
        
        if sim_results:
            data, sf_total, am_total = sim_results
            df = pd.DataFrame(data)
            
            # Area Chart
            fig = px.area(df, x="GW", y=["Set & Forget", "Actual Performance"],
                          title="Management Alpha: Set & Forget vs. Actual Performance",
                          color_discrete_map={"Set & Forget": "#ef5350", "Actual Performance": "#66bb6a"},
                          template="plotly_white")
            
            fig.update_layout(
                title={
                    'text': "Management Alpha: Original vs. Actual",
                    'subtitle': {'text': "❗Actual performance doesn't include additional points from chips like 3️⃣Triple Captain and 🪑Bench Boost"}
                },
                hovermode="x unified"
            )
            fig.update_traces(stackgroup=None)
            st.plotly_chart(fig, use_container_width=True)
            
            # Metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Set & Forget", f"{sf_total} pts")
            m2.metric("Actual Decisions", f"{am_total} pts")
            
            diff = am_total - sf_total
            m3.metric("Management Alpha", f"{diff} pts", delta=int(diff))
            
            if diff < 0:
                st.warning(f"Ouch! You would be {abs(diff)} points better off if you had never touched your team.")
            else:
                st.success(f"Great job! Your transfers have added {diff} points to your total.")
        else:
            st.error("Team ID not found. Please check your sidebar entry.")