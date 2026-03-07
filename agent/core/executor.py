"""
Workflow executor with parallel execution support
"""
import asyncio
from typing import Dict, Any, List, Set, Optional
from collections import defaultdict, deque
from datetime import datetime

from agent.core.context import AgentContext
from agent.core.memory import MemoryManager
from agent.llm.client import LLMClient
from agent.skills.base import skill_registry
from agent.mcp.client import mcp_manager
from core.exceptions import AgentError
from models import WorkflowExecution, NodeExecution, ExecutionStatus


class WorkflowExecutor:
    """
    Executes workflows with support for parallel node execution
    """
    
    def __init__(self, workflow_config: Dict[str, Any], context: AgentContext):
        self.config = workflow_config
        self.context = context
        self.nodes: Dict[str, Dict] = {}
        self.edges: Dict[str, List[Dict]] = defaultdict(list)
        self.node_results: Dict[str, Any] = {}
        self.llm_client = LLMClient(context.llm_config or {})
    
    def build_graph(self):
        """Build execution graph from nodes and edges"""
        # Index nodes by ID
        for node in self.config.get("nodes", []):
            node_id = node.get("id")
            self.nodes[node_id] = node
        
        # Build edge adjacency list
        for edge in self.config.get("edges", []):
            source = edge.get("source")
            target = edge.get("target")
            condition = edge.get("condition", {})
            self.edges[source].append({
                "target": target,
                "condition": condition
            })
    
    def topological_sort(self) -> List[str]:
        """
        Perform topological sort to determine execution order
        Returns nodes in valid execution order
        """
        # Build in-degree map
        in_degree: Dict[str, int] = {node_id: 0 for node_id in self.nodes}
        
        for source, targets in self.edges.items():
            for edge in targets:
                target = edge["target"]
                if target in in_degree:
                    in_degree[target] += 1
        
        # Find all nodes with no incoming edges (start nodes)
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        
        result = []
        while queue:
            node_id = queue.popleft()
            result.append(node_id)
            
            for edge in self.edges.get(node_id, []):
                target = edge["target"]
                if target in in_degree:
                    in_degree[target] -= 1
                    if in_degree[target] == 0:
                        queue.append(target)
        
        if len(result) != len(self.nodes):
            raise AgentError("Workflow contains a cycle")
        
        return result
    
    def get_parallel_groups(self) -> List[List[str]]:
        """
        Group nodes that can be executed in parallel
        Returns list of node groups for each execution level
        """
        in_degree: Dict[str, int] = {node_id: 0 for node_id in self.nodes}
        
        for source, targets in self.edges.items():
            for edge in targets:
                target = edge["target"]
                if target in in_degree:
                    in_degree[target] += 1
        
        groups = []
        remaining = set(self.nodes.keys())
        
        while remaining:
            # Find all nodes with in_degree 0
            current_group = [
                node_id for node_id in remaining
                if in_degree[node_id] == 0
            ]
            
            if not current_group:
                raise AgentError("Workflow contains a cycle")
            
            groups.append(current_group)
            
            # Update in_degrees
            for node_id in current_group:
                remaining.remove(node_id)
                for edge in self.edges.get(node_id, []):
                    target = edge["target"]
                    if target in in_degree:
                        in_degree[target] -= 1
        
        return groups
    
    async def execute(self) -> Dict[str, Any]:
        """Execute workflow with parallel node support"""
        self.build_graph()
        
        # Get parallel execution groups
        groups = self.get_parallel_groups()
        
        for group in groups:
            # Execute nodes in parallel within group
            tasks = [self.execute_node(node_id) for node_id in group]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Store results
            for node_id, result in zip(group, results):
                if isinstance(result, Exception):
                    raise AgentError(f"Node {node_id} failed: {str(result)}")
                self.node_results[node_id] = result
        
        # Return final result
        end_nodes = [n for n in self.nodes.values() if n.get("type") == "end"]
        if end_nodes:
            return self.node_results.get(end_nodes[0].get("id"), {})
        
        return self.node_results
    
    async def execute_node(self, node_id: str) -> Any:
        """Execute a single node"""
        node = self.nodes.get(node_id)
        if not node:
            raise AgentError(f"Node {node_id} not found")
        
        node_type = node.get("type")
        config = node.get("config", {})
        
        if node_type == "start":
            return self.context.input_data
        
        elif node_type == "end":
            return self.node_results
        
        elif node_type == "llm":
            return await self._execute_llm_node(config)
        
        elif node_type == "skill":
            return await self._execute_skill_node(config)
        
        elif node_type == "tool":
            return await self._execute_tool_node(config)
        
        elif node_type == "condition":
            return await self._execute_condition_node(config)
        
        elif node_type == "parallel":
            return await self._execute_parallel_node(config)
        
        elif node_type == "code":
            return await self._execute_code_node(config)
        
        elif node_type == "transform":
            return self._execute_transform_node(config)
        
        else:
            raise AgentError(f"Unknown node type: {node_type}")
    
    async def _execute_llm_node(self, config: Dict) -> str:
        """Execute LLM node"""
        prompt_template = config.get("prompt_template", "")
        prompt = self._render_template(prompt_template)
        
        response = await self.llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            model=config.get("model"),
            temperature=config.get("temperature", 0.7)
        )
        
        return response.get("content", "")
    
    async def _execute_skill_node(self, config: Dict) -> Any:
        """Execute skill node"""
        skill_name = config.get("skill_name")
        params = self._resolve_params(config.get("params", {}))
        
        skill = skill_registry.get(skill_name)
        if not skill:
            raise AgentError(f"Skill not found: {skill_name}")
        
        return await skill.execute(self.context, params)
    
    async def _execute_tool_node(self, config: Dict) -> Any:
        """Execute MCP tool node"""
        tool_name = config.get("tool_name")
        arguments = self._resolve_params(config.get("arguments", {}))
        
        return await mcp_manager.call_tool(tool_name, arguments)
    
    async def _execute_condition_node(self, config: Dict) -> bool:
        """Execute condition node"""
        expression = config.get("expression", "true")
        # Simple evaluation (in production, use safe eval)
        return self._evaluate_condition(expression)
    
    async def _execute_parallel_node(self, config: Dict) -> List[Any]:
        """Execute parallel node"""
        branches = config.get("branches", [])
        tasks = []
        
        for branch in branches:
            # Execute each branch
            for node_id in branch.get("nodes", []):
                tasks.append(self.execute_node(node_id))
        
        return await asyncio.gather(*tasks)
    
    async def _execute_code_node(self, config: Dict) -> Any:
        """Execute code node (sandboxed)"""
        # TODO: Implement sandboxed code execution
        code = config.get("code", "")
        return {"result": "code_execution_placeholder"}
    
    def _execute_transform_node(self, config: Dict) -> Any:
        """Execute data transformation node"""
        import copy
        data = copy.deepcopy(self.node_results)
        
        # Apply transformations
        for transform in config.get("transforms", []):
            op = transform.get("op")
            path = transform.get("path")
            value = transform.get("value")
            
            if op == "set":
                self._set_nested(data, path, value)
            elif op == "delete":
                self._delete_nested(data, path)
        
        return data
    
    def _render_template(self, template: str) -> str:
        """Render template with context variables"""
        result = template
        for key, value in self.context.variables.items():
            result = result.replace(f"{{{key}}}", str(value))
        for key, value in self.node_results.items():
            result = result.replace(f"{{results.{key}}}", str(value))
        return result
    
    def _resolve_params(self, params: Dict) -> Dict:
        """Resolve parameter references"""
        import copy
        resolved = copy.deepcopy(params)
        
        for key, value in resolved.items():
            if isinstance(value, str) and value.startswith("$"):
                # Reference to node result
                ref = value[1:]
                if ref in self.node_results:
                    resolved[key] = self.node_results[ref]
        
        return resolved
    
    def _evaluate_condition(self, expression: str) -> bool:
        """Evaluate condition expression"""
        # Replace variables
        expr = self._render_template(expression)
        
        # Simple evaluation
        try:
            return bool(eval(expr, {"__builtins__": {}}, self.node_results))
        except:
            return False
    
    def _set_nested(self, data: Dict, path: str, value: Any):
        """Set nested dictionary value"""
        keys = path.split(".")
        for key in keys[:-1]:
            data = data.setdefault(key, {})
        data[keys[-1]] = value
    
    def _delete_nested(self, data: Dict, path: str):
        """Delete nested dictionary key"""
        keys = path.split(".")
        for key in keys[:-1]:
            data = data.get(key, {})
        if keys[-1] in data:
            del data[keys[-1]]