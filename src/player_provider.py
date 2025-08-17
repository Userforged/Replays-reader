import json
import requests
import time
from datetime import datetime, timedelta, date
from typing import List, Dict


class PlayerProvider:
    """Provides SF6 player names from API sources with local caching."""
    
    def __init__(self, config_file: str = "players.json"):
        """
        Initialize PlayerProvider with configuration file.
        
        Args:
            config_file: Path to players.json configuration file
        """
        self.config_file = config_file
        self.config = self._load_config()
        
    def _load_config(self) -> Dict:
        """Load configuration from players.json file."""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Ensure required structure exists
            if 'players' not in config:
                config['players'] = []
            
            # Add last_updated if missing
            if 'last_updated' not in config:
                config['last_updated'] = None
                
            return config
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Player configuration file '{self.config_file}' not found")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file '{self.config_file}': {e}")
    
    def _save_config(self):
        """Save configuration back to players.json file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save config file: {e}")
    
    def _is_cache_valid(self) -> bool:
        """Check if cached player data is still valid (less than 1 month old)."""
        last_updated_str = self.config.get('last_updated')
        
        if not last_updated_str:
            return False
            
        try:
            last_updated_date = datetime.strptime(last_updated_str, '%Y-%m-%d').date()
            today = date.today()
            
            # Cache is valid if less than 1 month old
            one_month_ago = today - timedelta(days=30)
            return last_updated_date > one_month_ago
            
        except (ValueError, TypeError):
            return False
    
    def _fetch_players_from_api(self) -> List[str]:
        """Fetch player names from the configured API with pagination support."""
        base_url = self.config.get('url')
        if not base_url:
            print("Warning: No API URL configured in players.json")
            return []
        
        all_players = []
        current_url = base_url
        page_count = 0
        total_items = None
        
        try:
            while current_url:
                page_count += 1
                
                # Rate limiting: 1 call per second (except for first call)
                if page_count > 1:
                    time.sleep(1.0)
                
                print(f"Fetching page {page_count} from API: {current_url}")
                
                response = requests.get(current_url, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                # Get total items count from first page
                if page_count == 1 and 'totalItems' in data:
                    total_items = data['totalItems']
                    print(f"API reports {total_items} total players across all pages")
                
                # Handle different API response formats
                page_players = []
                
                if isinstance(data, list):
                    # Direct list of player names
                    page_players = [str(player).strip() for player in data if player]
                elif isinstance(data, dict):
                    # Check common API response patterns
                    if 'players' in data:
                        page_players = [str(p).strip() for p in data['players'] if p]
                    elif 'data' in data:
                        page_players = [str(p).strip() for p in data['data'] if p]
                    elif 'member' in data:  # JSON-LD Collection format
                        members = data['member']
                        if isinstance(members, list):
                            for item in members:
                                if isinstance(item, dict):
                                    # Extract player object with all name variations
                                    player_obj = {}
                                    
                                    # Primary name (required)
                                    name = item.get('name')
                                    if name:
                                        player_obj['name'] = str(name).strip()
                                        
                                        # Additional name variations (optional)
                                        if item.get('shortName'):
                                            player_obj['shortName'] = str(item['shortName']).strip()
                                        if item.get('originalName'):
                                            player_obj['originalName'] = str(item['originalName']).strip()
                                        if item.get('country'):
                                            player_obj['country'] = str(item['country']).strip()
                                        
                                        page_players.append(player_obj)
                    elif '@graph' in data:  # JSON-LD format
                        graph = data['@graph']
                        if isinstance(graph, list):
                            for item in graph:
                                if isinstance(item, dict):
                                    # Extract player object with all name variations
                                    player_obj = {}
                                    
                                    # Primary name (required)
                                    name = item.get('name') or item.get('player_name') or item.get('nickname')
                                    if name:
                                        player_obj['name'] = str(name).strip()
                                        
                                        # Additional name variations (optional)
                                        if item.get('shortName'):
                                            player_obj['shortName'] = str(item['shortName']).strip()
                                        if item.get('originalName'):
                                            player_obj['originalName'] = str(item['originalName']).strip()
                                        if item.get('country'):
                                            player_obj['country'] = str(item['country']).strip()
                                        
                                        page_players.append(player_obj)
                    else:
                        print(f"Warning: Unknown API response format: {list(data.keys())}")
                        break
                
                # Add this page's players to the total
                all_players.extend(page_players)
                print(f"Page {page_count}: Found {len(page_players)} players (total so far: {len(all_players)})")
                
                # Check for next page in pagination
                current_url = None
                if isinstance(data, dict) and 'view' in data:
                    view = data['view']
                    if isinstance(view, dict) and 'next' in view:
                        next_url = view['next']
                        if next_url:
                            # Convert relative URL to absolute if needed
                            if next_url.startswith('/'):
                                from urllib.parse import urljoin, urlparse
                                parsed_base = urlparse(base_url)
                                base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
                                current_url = urljoin(base_domain, next_url)
                            else:
                                current_url = next_url
            
            # Remove duplicates based on primary name and filter empty objects
            seen_names = set()
            unique_players = []
            for player in all_players:
                if isinstance(player, dict) and player.get('name'):
                    primary_name = player['name']
                    if primary_name not in seen_names:
                        seen_names.add(primary_name)
                        unique_players.append(player)
            
            final_count = len(unique_players)
            print(f"Successfully fetched {final_count} unique players from {page_count} pages")
            if total_items:
                print(f"Retrieved {final_count}/{total_items} players from API")
            
            return unique_players
            
        except requests.RequestException as e:
            print(f"Error fetching players from API: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"Error parsing API response: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error fetching players: {e}")
            return []
    
    def refresh_cache(self) -> bool:
        """
        Refresh player cache from API.
        
        Returns:
            True if refresh was successful, False otherwise
        """
        print("Refreshing player cache from API...")
        
        api_players = self._fetch_players_from_api()
        
        if not api_players:
            print("Warning: No players fetched from API, keeping existing cache")
            return False
        
        # Update config with new data
        self.config['players'] = api_players
        self.config['last_updated'] = date.today().strftime('%Y-%m-%d')
        
        # Save to file
        self._save_config()
        
        print(f"Cache refreshed successfully with {len(api_players)} players")
        return True
    
    def get_all_players(self, force_refresh: bool = False) -> List[str]:
        """
        Get all player names (cached + static).
        
        Args:
            force_refresh: Force refresh from API even if cache is valid
            
        Returns:
            List of all known player names
        """
        # Check if we need to refresh cache
        if force_refresh or not self._is_cache_valid():
            self.refresh_cache()
        
        # Get API players (now objects with name variations)
        api_players = self.config.get('players', [])
        static_players = self.config.get('static_players', [])
        
        # Extract all name variations from API players
        all_names = []
        
        for player in api_players:
            if isinstance(player, dict):
                # Add all available name variations
                if player.get('name'):
                    all_names.append(player['name'])
                if player.get('shortName'):
                    all_names.append(player['shortName'])
                if player.get('originalName'):
                    all_names.append(player['originalName'])
            elif isinstance(player, str):
                # Backward compatibility for old format
                all_names.append(player)
        
        # Add static players (should be strings)
        for player in static_players:
            if isinstance(player, str):
                all_names.append(player)
        
        # Remove duplicates and empty strings
        unique_names = list(set([name.strip() for name in all_names if name and name.strip()]))
        
        return sorted(unique_names)
    
    def search_player(self, query: str, threshold: float = 0.6) -> List[str]:
        """
        Search for players matching a query using fuzzy matching.
        
        Args:
            query: Search query
            threshold: Minimum similarity threshold (0.0-1.0)
            
        Returns:
            List of matching player names sorted by similarity
        """
        if not query or len(query.strip()) < 2:
            return []
        
        try:
            from rapidfuzz import process, fuzz
        except ImportError:
            print("Warning: rapidfuzz not available, falling back to exact matching")
            all_players = self.get_all_players()
            query_upper = query.upper()
            return [p for p in all_players if query_upper in p.upper()]
        
        all_players = self.get_all_players()
        
        # Use rapidfuzz for fuzzy matching
        matches = process.extract(
            query, 
            all_players, 
            scorer=fuzz.ratio,
            limit=10
        )
        
        # Filter by threshold and return names only
        return [match[0] for match in matches if match[1] >= threshold * 100]
    
    def get_cache_info(self) -> Dict:
        """Get information about the current cache."""
        is_valid = self._is_cache_valid()
        last_updated = self.config.get('last_updated')
        
        # Calculate days since last update
        days_since_update = None
        if last_updated:
            try:
                last_updated_date = datetime.strptime(last_updated, '%Y-%m-%d').date()
                days_since_update = (date.today() - last_updated_date).days
            except (ValueError, TypeError):
                pass
        
        # Count unique players (objects) vs total names (including variations)
        api_players = self.config.get('players', [])
        unique_player_objects = len([p for p in api_players if isinstance(p, dict)])
        
        return {
            'is_valid': is_valid,
            'last_updated': last_updated,
            'days_since_update': days_since_update,
            'unique_players': unique_player_objects,
            'static_player_count': len(self.config.get('static_players', [])),
            'total_names': len(self.get_all_players())
        }