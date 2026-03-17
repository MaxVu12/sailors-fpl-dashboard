import streamlit as st
import pandas as pd
import requests

# This keeps your app fast by not hitting the API on every single click
@st.cache_data(ttl=600) 
def get_data(url):
    return requests.get(url).json()

class FPLMoneyLeague:
    def __init__(self, league_id):
        self.league_id = league_id
        self.bootstrap_url = 'https://fantasy.premierleague.com/api/bootstrap-static/'
        self.api_url = f"https://fantasy.premierleague.com/api/leagues-classic/{self.league_id}/standings/"
        
        # Your specific money mapping
        self.weekly_prize_mapping = {
            1: 45, 2: 35, 3: 25, 4: 20, 5: 15, 6: 10, 7: 0, 
            8: -5, 9: -10, 10: -10, 11: -15, 12: -20, 13: -25, 14: -30, 15: -35
        }

    def get_live_standings(self):
            data = get_data(self.api_url)
            
            # DEBUG: This helps us see the actual API response if it fails
            # st.write(data) 

            # Check if 'standings' exists in the response
            if 'standings' not in data:
                return pd.DataFrame({"Error": ["Could not find standings. Check if your League ID is a Classic League."]})
            
            if not data['standings'].get('results'):
                return pd.DataFrame({"Error": ["League hasn't started or no results found yet."]})
            
            df = pd.json_normalize(data['standings']['results'])
            
            # Clean up the dataframe
            df = df[['rank', 'player_name', 'entry_name', 'event_total', 'total']]
            df.columns = ['Rank', 'Manager', 'Team Name', 'GW Points', 'Total Points']
            
            # Calculate the money logic live
            df['Weekly Cash'] = df['Rank'].map(self.weekly_prize_mapping).fillna(0)
            
            return df

# --- STREAMLIT UI ---
st.set_page_config(page_title="Sailors FPL", page_icon="⚽")
st.title("⚓ Sailors FPL Money League")

# Sidebar input for your league
league_id = st.sidebar.text_input("Enter FPL League ID", value="123456") # Put your real ID here

if st.button('Fetch Live Standings'):
    fpl = FPLMoneyLeague(league_id)
    with st.spinner('Calculating profits...'):
        df = fpl.get_live_standings()
        
        # Display a summary metric
        top_row = df.iloc[0]
        st.metric(label="Current GW Leader", value=top_row['Manager'], delta=f"{top_row['GW Points']} pts")
        
        # Show the table
        st.write("### Weekly Breakdown")
        st.dataframe(
            df.style.format({'Weekly Cash': '${:.2f}'})
                    .highlight_max(axis=0, subset=['GW Points'], color='lightgreen')
        )