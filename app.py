import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os

# Page config
st.set_page_config(
    page_title="South African Music Playlist Analytics",
    page_icon="🎵",
    layout="wide"
)

# Initialize Spotify client
@st.cache_resource
def init_spotify():
    client_credentials_manager = SpotifyClientCredentials(
        client_id=st.secrets["SPOTIFY_CLIENT_ID"],
        client_secret=st.secrets["SPOTIFY_CLIENT_SECRET"]
    )
    return spotipy.Spotify(client_credentials_manager=client_credentials_manager)

# Extract playlist ID from URL
def get_playlist_id(url):
    return url.split("/")[-1].split("?")[0]

# Load historical data from CSV
def load_historical_data():
    if os.path.exists("playlist_history.csv"):
        return pd.read_csv("playlist_history.csv", parse_dates=['date'])
    return pd.DataFrame(columns=['date', 'saves', 'total_tracks', 'avg_popularity'])

# Save historical data to CSV
def save_historical_data(df):
    df.to_csv("playlist_history.csv", index=False)

# Load track popularity history
def load_track_history():
    if os.path.exists("track_popularity_history.csv"):
        return pd.read_csv("track_popularity_history.csv", parse_dates=['date'])
    return pd.DataFrame(columns=['date', 'track_id', 'track_name', 'artist', 'popularity'])

# Save track popularity history
def save_track_history(df):
    df.to_csv("track_popularity_history.csv", index=False)

# Get playlist data - Fixed caching issue
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_playlist_data(_sp, playlist_id):
    playlist = _sp.playlist(playlist_id)
    
    # Get all tracks (handle playlists with more than 100 tracks)
    tracks = []
    results = _sp.playlist_tracks(playlist_id)
    tracks.extend(results['items'])
    
    while results['next']:
        results = _sp.next(results)
        tracks.extend(results['items'])
    
    # Extract track information
    track_data = []
    for item in tracks:
        track = item['track']
        if track:  # Check if track exists (not deleted)
            track_data.append({
                'track_id': track['id'],
                'name': track['name'],
                'artist': ', '.join([artist['name'] for artist in track['artists']]),
                'album': track['album']['name'],
                'popularity': track['popularity'],
                'duration_ms': track['duration_ms'],
                'release_date': track['album']['release_date'],
                'preview_url': track['preview_url'],
                'external_url': track['external_urls']['spotify']
            })
    
    return playlist, pd.DataFrame(track_data)

# Update daily statistics
def update_daily_stats(playlist_info, tracks_df):
    today = pd.Timestamp.now().normalize()
    
    # Load existing data
    hist_df = load_historical_data()
    track_hist_df = load_track_history()
    
    # Check if today's data already exists
    if not hist_df.empty and today in hist_df['date'].values:
        return hist_df, track_hist_df
    
    # Add today's playlist statistics
    new_row = pd.DataFrame([{
        'date': today,
        'saves': playlist_info['followers']['total'],
        'total_tracks': len(tracks_df),
        'avg_popularity': tracks_df['popularity'].mean()
    }])
    
    hist_df = pd.concat([hist_df, new_row], ignore_index=True)
    save_historical_data(hist_df)
    
    # Add today's track popularity data
    today_tracks = tracks_df[['track_id', 'name', 'artist', 'popularity']].copy()
    today_tracks['date'] = today
    
    track_hist_df = pd.concat([track_hist_df, today_tracks], ignore_index=True)
    save_track_history(track_hist_df)
    
    return hist_df, track_hist_df

# Main app
def main():
    st.title("🎵 South African Music Playlist Analytics")
    st.markdown("### Tracking playlist growth and analyzing track popularity")
    
    # Initialize Spotify
    try:
        sp = init_spotify()
    except Exception as e:
        st.error("Failed to initialize Spotify client. Please check your credentials in Streamlit secrets.")
        st.stop()
    
    # Playlist URL
    playlist_url = "https://open.spotify.com/playlist/4fdUWePS7vpy3r1GiZtv1L"
    playlist_id = get_playlist_id(playlist_url)
    
    # Get playlist data
    try:
        playlist_info, tracks_df = get_playlist_data(sp, playlist_id)
    except Exception as e:
        st.error(f"Failed to fetch playlist data: {str(e)}")
        st.stop()
    
    # Update daily statistics
    hist_df, track_hist_df = update_daily_stats(playlist_info, tracks_df)
    
    # Display playlist info
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Playlist Name", playlist_info['name'])
    with col2:
        st.metric("Total Tracks", len(tracks_df))
    with col3:
        st.metric("Followers", f"{playlist_info['followers']['total']:,}")
    with col4:
        st.metric("Owner", playlist_info['owner']['display_name'])
    
    # Tabs for different views
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Growth Tracking", "🎯 Track Popularity", "📊 Playlist Analysis", "🎵 Track Details", "📁 Data Export"])
    
    with tab1:
        st.header("Playlist Growth Over Time")
        
        if len(hist_df) > 1:
            # Calculate daily changes
            hist_df = hist_df.sort_values('date')
            hist_df['daily_growth'] = hist_df['saves'].diff().fillna(0)
            hist_df['growth_rate'] = (hist_df['saves'].pct_change() * 100).fillna(0)
            
            # Create subplots
            col1, col2 = st.columns(2)
            
            with col1:
                # Line chart for saves
                fig_saves = go.Figure()
                fig_saves.add_trace(go.Scatter(
                    x=hist_df['date'],
                    y=hist_df['saves'],
                    mode='lines+markers',
                    name='Total Saves',
                    line=dict(color='#1DB954', width=3),
                    marker=dict(size=8)
                ))
                
                fig_saves.update_layout(
                    title="Total Playlist Saves",
                    xaxis_title="Date",
                    yaxis_title="Total Saves",
                    hovermode='x unified',
                    height=400
                )
                
                st.plotly_chart(fig_saves, use_container_width=True)
            
            with col2:
                # Bar chart for daily growth
                fig_growth = go.Figure()
                fig_growth.add_trace(go.Bar(
                    x=hist_df['date'],
                    y=hist_df['daily_growth'],
                    name='Daily Growth',
                    marker_color=hist_df['daily_growth'].apply(lambda x: '#1DB954' if x >= 0 else '#FF6B6B')
                ))
                
                fig_growth.update_layout(
                    title="Daily Save Growth",
                    xaxis_title="Date",
                    yaxis_title="New Saves",
                    height=400
                )
                
                st.plotly_chart(fig_growth, use_container_width=True)
            
            # Average popularity over time
            fig_pop = go.Figure()
            fig_pop.add_trace(go.Scatter(
                x=hist_df['date'],
                y=hist_df['avg_popularity'],
                mode='lines+markers',
                name='Avg Popularity',
                line=dict(color='#FF6B6B', width=2),
                marker=dict(size=6)
            ))
            
            fig_pop.update_layout(
                title="Average Track Popularity Over Time",
                xaxis_title="Date",
                yaxis_title="Average Popularity Score",
                hovermode='x unified',
                height=400
            )
            
            st.plotly_chart(fig_pop, use_container_width=True)
            
            # Growth metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                total_growth = hist_df['saves'].iloc[-1] - hist_df['saves'].iloc[0]
                st.metric("Total Growth", f"+{total_growth:,}")
            with col2:
                avg_daily_growth = hist_df['daily_growth'][1:].mean()
                st.metric("Avg Daily Growth", f"+{avg_daily_growth:.1f}")
            with col3:
                growth_rate = ((hist_df['saves'].iloc[-1] / hist_df['saves'].iloc[0]) - 1) * 100
                st.metric("Overall Growth Rate", f"{growth_rate:.1f}%")
            with col4:
                days_tracked = len(hist_df)
                st.metric("Days Tracked", days_tracked)
            
        else:
            st.info("Growth tracking will be available after collecting data for multiple days. Check back tomorrow!")
            st.metric("Current Saves", f"{playlist_info['followers']['total']:,}")
    
    with tab2:
        st.header("Track Popularity Analysis")
        
        # Top tracks by popularity
        top_tracks = tracks_df.nlargest(20, 'popularity')
        
        fig_popularity = px.bar(
            top_tracks,
            x='popularity',
            y='name',
            orientation='h',
            color='popularity',
            color_continuous_scale='Viridis',
            labels={'name': 'Track', 'popularity': 'Popularity Score'},
            title="Top 20 Most Popular Tracks"
        )
        
        fig_popularity.update_layout(
            height=600,
            showlegend=False,
            yaxis={'categoryorder': 'total ascending'}
        )
        
        st.plotly_chart(fig_popularity, use_container_width=True)
        
        # Track popularity changes over time (if we have historical data)
        if len(track_hist_df) > 0:
            st.subheader("Track Popularity Trends")
            
            # Select tracks to analyze
            selected_tracks = st.multiselect(
                "Select tracks to view popularity trends",
                options=tracks_df['name'].unique(),
                default=top_tracks['name'].head(5).tolist()
            )
            
            if selected_tracks:
                # Filter historical data for selected tracks
                trend_data = track_hist_df[track_hist_df['name'].isin(selected_tracks)]
                
                fig_trends = px.line(
                    trend_data,
                    x='date',
                    y='popularity',
                    color='name',
                    title="Track Popularity Trends",
                    labels={'popularity': 'Popularity Score', 'name': 'Track'}
                )
                
                fig_trends.update_layout(height=500)
                st.plotly_chart(fig_trends, use_container_width=True)
        
        # Popularity distribution
        fig_dist = px.histogram(
            tracks_df,
            x='popularity',
            nbins=20,
            title="Track Popularity Distribution",
            labels={'popularity': 'Popularity Score', 'count': 'Number of Tracks'}
        )
        
        fig_dist.update_layout(
            showlegend=False,
            bargap=0.1
        )
        
        st.plotly_chart(fig_dist, use_container_width=True)
    
    with tab3:
        st.header("Playlist Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Artists with most tracks
            artist_counts = tracks_df['artist'].value_counts().head(15)
            
            fig_artists = px.pie(
                values=artist_counts.values,
                names=artist_counts.index,
                title="Top 15 Artists by Track Count"
            )
            
            st.plotly_chart(fig_artists, use_container_width=True)
        
        with col2:
            # Average track duration
            tracks_df['duration_min'] = tracks_df['duration_ms'] / 60000
            
            fig_duration = px.box(
                tracks_df,
                y='duration_min',
                title="Track Duration Distribution",
                labels={'duration_min': 'Duration (minutes)'}
            )
            
            st.plotly_chart(fig_duration, use_container_width=True)
        
        # Release date analysis - handle different date formats
        def extract_year(date_str):
            if pd.isna(date_str):
                return None
            # If it's just a year (4 digits)
            if len(str(date_str)) == 4:
                return int(date_str)
            # If it's YYYY-MM or YYYY-MM-DD
            else:
                return int(str(date_str).split('-')[0])
        
        tracks_df['release_year'] = tracks_df['release_date'].apply(extract_year)
        # Filter out None values before counting
        year_counts = tracks_df['release_year'].dropna().value_counts().sort_index()
        
        fig_years = px.line(
            x=year_counts.index,
            y=year_counts.values,
            title="Tracks by Release Year",
            labels={'x': 'Year', 'y': 'Number of Tracks'}
        )
        
        fig_years.update_traces(mode='lines+markers')
        st.plotly_chart(fig_years, use_container_width=True)
    
    with tab4:
        st.header("Track Details")
        
        # Search functionality
        search_term = st.text_input("Search tracks by name or artist", "")
        
        if search_term:
            filtered_df = tracks_df[
                tracks_df['name'].str.contains(search_term, case=False) |
                tracks_df['artist'].str.contains(search_term, case=False)
            ]
        else:
            filtered_df = tracks_df
        
        # Sort options
        sort_by = st.selectbox(
            "Sort by",
            ["Popularity", "Track Name", "Artist", "Release Date"]
        )
        
        sort_mapping = {
            "Popularity": "popularity",
            "Track Name": "name",
            "Artist": "artist",
            "Release Date": "release_date"
        }
        
        ascending = sort_by != "Popularity"
        filtered_df = filtered_df.sort_values(sort_mapping[sort_by], ascending=ascending)
        
        # Display tracks
        st.dataframe(
            filtered_df[['name', 'artist', 'album', 'popularity', 'release_date']],
            use_container_width=True,
            height=600
        )
    
    with tab5:
        st.header("Export Historical Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Playlist Statistics History")
            if not hist_df.empty:
                st.dataframe(hist_df, use_container_width=True)
                csv1 = hist_df.to_csv(index=False)
                st.download_button(
                    label="Download Playlist History CSV",
                    data=csv1,
                    file_name=f"playlist_history_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No historical data available yet")
        
        with col2:
            st.subheader("Current Track Data")
            csv2 = tracks_df.to_csv(index=False)
            st.download_button(
                label="Download Current Tracks CSV",
                data=csv2,
                file_name=f"current_tracks_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
            
            if not track_hist_df.empty:
                st.subheader("Track Popularity History")
                # Show summary of track history
                track_summary = track_hist_df.groupby('date').agg({
                    'track_id': 'count',
                    'popularity': 'mean'
                }).rename(columns={'track_id': 'tracks_count', 'popularity': 'avg_popularity'})
                
                st.dataframe(track_summary, use_container_width=True)
                
                csv3 = track_hist_df.to_csv(index=False)
                st.download_button(
                    label="Download Track Popularity History CSV",
                    data=csv3,
                    file_name=f"track_popularity_history_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

if __name__ == "__main__":
    main()