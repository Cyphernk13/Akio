# music/nodes.py
import asyncio
import aiohttp
import json
import os
import time
import random
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

PUBLIC_API_ALL = "https://lavalink-list.ajieblogs.eu.org/All"
PUBLIC_API_SSL = "https://lavalink-list.ajieblogs.eu.org/SSL"
PUBLIC_API_NONSSL = "https://lavalink-list.ajieblogs.eu.org/NonSSL"

@dataclass
class NodeInfo:
    """Information about a Lavalink node."""
    host: str
    port: int
    password: str
    secure: bool
    identifier: str
    version: str = "v4"
    load: float = 0.0
    players: int = 0
    playing_players: int = 0
    uptime: str = ""
    last_health_check: float = field(default_factory=time.time)
    health_failures: int = 0
    is_healthy: bool = True
    latency: float = 999.0
    
    @property
    def score(self) -> float:
        """Calculate node score for load balancing (lower is better)."""
        if not self.is_healthy:
            return 9999.0
        
        # Score based on load, player count, latency, and health
        load_score = self.load * 100
        player_score = (self.players / 500) * 50  # Normalize player count
        latency_score = min(self.latency / 10, 100)  # Cap latency impact
        health_penalty = self.health_failures * 20
        
        return load_score + player_score + latency_score + health_penalty


class EnhancedLavalinkNodeManager:
    """Enhanced Lavalink node manager with smart failover, load balancing, and health monitoring."""

    def __init__(self, bot):
        self.bot = bot
        self._refresh_task: Optional[asyncio.Task] = None
        self._health_task: Optional[asyncio.Task] = None
        self._nodes: Dict[str, NodeInfo] = {}
        self._preferred_versions = ["v4", "v5"]
        self._max_nodes = 10
        self._health_check_interval = 300  # 5 minutes
        self._refresh_interval = 600  # 10 minutes
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                connector=aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
            )
        return self._session

    async def fetch_public_nodes(self) -> List[Dict[str, Any]]:
        """Fetch nodes from public APIs with fallback."""
        apis = [PUBLIC_API_SSL, PUBLIC_API_ALL, PUBLIC_API_NONSSL]
        
        for api_url in apis:
            try:
                session = await self._get_session()
                async with session.get(api_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list) and len(data) > 0:
                            logger.info(f"[NodeManager] Fetched {len(data)} nodes from {api_url}")
                            return data
            except Exception as e:
                logger.warning(f"[NodeManager] Failed to fetch from {api_url}: {e}")
                continue
        
        logger.error("[NodeManager] All public APIs failed")
        return []

    async def check_node_health(self, node_info: NodeInfo) -> bool:
        """Check if a node is healthy by testing connectivity."""
        try:
            session = await self._get_session()
            url = f"{'https' if node_info.secure else 'http'}://{node_info.host}:{node_info.port}/version"
            
            start_time = time.time()
            async with session.get(
                url,
                headers={"Authorization": node_info.password},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                latency = (time.time() - start_time) * 1000
                
                if resp.status == 200:
                    node_info.latency = latency
                    node_info.last_health_check = time.time()
                    node_info.health_failures = 0
                    node_info.is_healthy = True
                    return True
                    
        except Exception as e:
            logger.warning(f"[NodeManager] Health check failed for {node_info.identifier}: {e}")
        
        node_info.health_failures += 1
        node_info.is_healthy = node_info.health_failures < 3
        return False

    async def get_node_stats(self, node_info: NodeInfo) -> Dict[str, Any]:
        """Get detailed stats from a node."""
        try:
            session = await self._get_session()
            url = f"{'https' if node_info.secure else 'http'}://{node_info.host}:{node_info.port}/stats"
            
            async with session.get(
                url,
                headers={"Authorization": node_info.password},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception:
            pass
        return {}

    def _existing_endpoints(self) -> set[Tuple[str, int, bool]]:
        """Get existing node endpoints to avoid duplicates."""
        endpoints: set[Tuple[str, int, bool]] = set()
        client = getattr(self.bot, 'lavalink', None)
        if not client:
            return endpoints
        
        # Check various possible attributes for nodes
        for attr in ('nodes', '_nodes', 'node_manager'):
            nodes = getattr(client, attr, None)
            if not nodes:
                continue
            
            try:
                if hasattr(nodes, 'nodes'):  # node_manager.nodes
                    nodes = nodes.nodes
                    
                node_list = list(nodes.values()) if isinstance(nodes, dict) else list(nodes)
                for node in node_list:
                    host = getattr(node, 'host', None)
                    port = getattr(node, 'port', None)
                    ssl = getattr(node, 'ssl', False)
                    if host and port:
                        endpoints.add((host, int(port), bool(ssl)))
            except Exception:
                continue
        
        return endpoints

    async def add_nodes_from_list(self, items: List[Dict[str, Any]], limit: int = 5) -> int:
        """Add nodes from a list with smart filtering and prioritization."""
        client = getattr(self.bot, 'lavalink', None)
        if not client:
            return 0
        
        existing = self._existing_endpoints()
        added = 0
        
        # Filter and sort nodes by preference
        filtered = []
        for item in items:
            version = str(item.get('version', '')).lower()
            if version in [v.lower() for v in self._preferred_versions]:
                filtered.append(item)
        
        # Sort by preference: secure first, then by version, then randomly
        filtered.sort(key=lambda x: (
            not bool(x.get('secure', False)),
            x.get('version', '') not in self._preferred_versions,
            random.random()
        ))
        
        for item in filtered:
            if added >= limit:
                break
                
            host = str(item.get('host', '')).strip()
            port = int(item.get('port', 443))
            password = str(item.get('password', '')).strip() or 'youshallnotpass'
            secure = bool(item.get('secure', False))
            identifier = item.get('identifier', f"{host}-{port}")
            version = item.get('version', 'v4')
            
            endpoint_key = (host, port, secure)
            if not host or endpoint_key in existing or identifier in self._nodes:
                continue
            
            # Create node info
            node_info = NodeInfo(
                host=host,
                port=port,
                password=password,
                secure=secure,
                identifier=identifier,
                version=version
            )
            
            # Test connectivity before adding
            if await self.check_node_health(node_info):
                try:
                    # Add to lavalink client
                    client.add_node(
                        host=host,
                        port=port,
                        password=password,
                        ssl=secure,
                        region='auto'  # Use auto region detection
                    )
                    
                    # Store node info
                    self._nodes[identifier] = node_info
                    existing.add(endpoint_key)
                    added += 1
                    
                    logger.info(f"[NodeManager] Added healthy node: {identifier}")
                    
                except Exception as e:
                    logger.warning(f"[NodeManager] Failed to add node {identifier}: {e}")
                    continue
            else:
                logger.warning(f"[NodeManager] Skipped unhealthy node: {identifier}")
        
        return added

    async def get_best_node(self) -> Optional[str]:
        """Get the best node based on performance metrics and health."""
        healthy_nodes = [node for node in self._nodes.values() if node.is_healthy]
        
        if not healthy_nodes:
            logger.warning("[NodeManager] No healthy nodes available!")
            return None
        
        # Enhanced scoring algorithm for optimal performance
        for node in healthy_nodes:
            # Base score from response time (lower is better)
            base_score = node.score
            
            # Performance adjustments
            performance_bonus = 0
            
            # Favor nodes with lower response times (faster)
            if node.response_time < 50:  # Very fast
                performance_bonus -= 0.2
            elif node.response_time < 100:  # Fast
                performance_bonus -= 0.1
            elif node.response_time > 300:  # Slow
                performance_bonus += 0.3
                
            # Favor nodes with fewer health failures
            if node.health_failures == 0:
                performance_bonus -= 0.1
            elif node.health_failures > 3:
                performance_bonus += 0.2
                
            # Favor newer versions (v4, v5)
            if hasattr(node, 'version'):
                if 'v5' in str(node.version):
                    performance_bonus -= 0.15
                elif 'v4' in str(node.version):
                    performance_bonus -= 0.1
                    
            # Apply final score
            node.performance_score = base_score + performance_bonus
        
        # Sort by performance score (lower is better)
        healthy_nodes.sort(key=lambda x: getattr(x, 'performance_score', x.score))
        best_node = healthy_nodes[0]
        
        logger.info(f"[NodeManager] 🚀 Selected optimal node: {best_node.identifier} "
                   f"(response: {best_node.response_time}ms, failures: {node.health_failures})")
        return best_node.identifier

    async def handle_node_failure(self, failed_node_id: str):
        """Handle node failure by marking it unhealthy and switching to backup."""
        if failed_node_id in self._nodes:
            self._nodes[failed_node_id].is_healthy = False
            self._nodes[failed_node_id].health_failures += 1
            logger.warning(f"[NodeManager] Marked node {failed_node_id} as unhealthy")
        
        # Try to switch to best available node
        best_node = await self.get_best_node()
        if best_node:
            logger.info(f"[NodeManager] Switching to backup node: {best_node}")
            # Here you could implement logic to migrate players if needed
        else:
            logger.error("[NodeManager] No backup nodes available!")

    async def bootstrap(self) -> None:
        """Bootstrap the node manager with initial nodes."""
        logger.info("[NodeManager] Starting bootstrap process...")
        
        # Load local override nodes first
        await self._load_override_nodes()
        
        # Fetch public nodes
        public_nodes = await self.fetch_public_nodes()
        if public_nodes:
            added = await self.add_nodes_from_list(public_nodes, limit=self._max_nodes - len(self._nodes))
            logger.info(f"[NodeManager] Added {added} public nodes during bootstrap")
        else:
            logger.warning("[NodeManager] No public nodes available during bootstrap")
        
        # Report total nodes
        total_nodes = len(self._nodes)
        logger.info(f"[NodeManager] Bootstrap complete. Total nodes: {total_nodes}")
        
        if total_nodes == 0:
            logger.error("[NodeManager] No nodes available! Bot may not function properly.")

    async def _load_override_nodes(self):
        """Load nodes from override file."""
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(base, 'nodes_override.json')
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    local_items = json.load(f)
                added = await self.add_nodes_from_list(local_items, limit=self._max_nodes)
                logger.info(f"[NodeManager] Added {added} override nodes")
        except Exception as e:
            logger.warning(f"[NodeManager] Failed to load override nodes: {e}")

    async def _health_check_loop(self):
        """Enhanced periodic health checking and performance optimization."""
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)
                
                logger.info("[NodeManager] 🔍 Starting enhanced health check cycle")
                tasks = []
                for node_info in self._nodes.values():
                    tasks.append(self.check_node_health(node_info))
                
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    healthy_count = sum(1 for r in results if r is True)
                    failed_nodes = []
                    
                    # Process results and update node health
                    for i, (node_info, result) in enumerate(zip(self._nodes.values(), results)):
                        if result is True:
                            # Reset failure count on successful health check
                            if node_info.health_failures > 0:
                                node_info.health_failures = max(0, node_info.health_failures - 1)
                        else:
                            node_info.health_failures += 1
                            node_info.is_healthy = False
                            if node_info.health_failures >= 5:
                                failed_nodes.append(node_info.identifier)
                    
                    # Remove persistently failing nodes
                    for node_id in failed_nodes:
                        logger.warning(f"[NodeManager] ❌ Removing persistently failing node: {node_id}")
                        del self._nodes[node_id]
                    
                    logger.info(f"[NodeManager] ✅ Health check complete: {healthy_count}/{len(tasks)} healthy, "
                               f"{len(failed_nodes)} removed")
                    
                    # Auto-optimize: If we have few healthy nodes, refresh immediately
                    if healthy_count < 3:
                        logger.warning("[NodeManager] ⚠️ Low healthy node count, triggering refresh...")
                        asyncio.create_task(self.refresh_nodes())
                
            except Exception as e:
                logger.error(f"[NodeManager] Health check loop error: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    async def _refresh_loop(self):
        """Periodic refresh of node list."""
        while True:
            try:
                await asyncio.sleep(self._refresh_interval)
                
                logger.debug("[NodeManager] Starting node refresh cycle")
                public_nodes = await self.fetch_public_nodes()
                if public_nodes:
                    # Only add new nodes if we have space
                    space_available = self._max_nodes - len([n for n in self._nodes.values() if n.is_healthy])
                    if space_available > 0:
                        added = await self.add_nodes_from_list(public_nodes, limit=space_available)
                        if added > 0:
                            logger.info(f"[NodeManager] Added {added} new nodes during refresh")
                
            except Exception as e:
                logger.error(f"[NodeManager] Refresh loop error: {e}")

    def start_background_tasks(self):
        """Start background monitoring tasks."""
        if self._refresh_task and not self._refresh_task.done():
            return
        
        loop = asyncio.get_running_loop()
        self._refresh_task = loop.create_task(self._refresh_loop())
        self._health_task = loop.create_task(self._health_check_loop())
        
        logger.info("[NodeManager] Background tasks started")

    async def cleanup(self):
        """Clean up resources."""
        if self._refresh_task:
            self._refresh_task.cancel()
        if self._health_task:
            self._health_task.cancel()
        if self._session and not self._session.closed:
            await self._session.close()

    def get_node_stats_summary(self) -> Dict[str, Any]:
        """Get summary of all node statistics."""
        healthy_nodes = [n for n in self._nodes.values() if n.is_healthy]
        total_players = sum(n.players for n in healthy_nodes)
        avg_load = sum(n.load for n in healthy_nodes) / len(healthy_nodes) if healthy_nodes else 0
        avg_latency = sum(n.latency for n in healthy_nodes) / len(healthy_nodes) if healthy_nodes else 999
        
        return {
            "total_nodes": len(self._nodes),
            "healthy_nodes": len(healthy_nodes),
            "total_players": total_players,
            "average_load": round(avg_load, 2),
            "average_latency": round(avg_latency, 2)
        }


# Keep the old class for backward compatibility
LavalinkNodeManager = EnhancedLavalinkNodeManager
