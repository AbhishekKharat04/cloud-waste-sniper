import json
import logging
import re
import os

logger = logging.getLogger(__name__)

class StateMapper:
    def __init__(self, state_file_path: str):
        self.state_file_path = state_file_path
        if not os.path.exists(state_file_path):
            raise FileNotFoundError(f"State file not found at {state_file_path}")

    def find_resource_by_id(self, aws_id: str) -> dict:
        """Parses terraform.tfstate and returns the tf_type and tf_name for a given AWS ID."""
        with open(self.state_file_path, 'r') as f:
            state_data = json.load(f)
        
        for resource in state_data.get("resources", []):
            mode = resource.get("mode")
            if mode != "managed":
                continue
            
            tf_type = resource.get("type")
            tf_name = resource.get("name")
            
            for instance in resource.get("instances", []):
                attributes = instance.get("attributes", {})
                if attributes.get("id") == aws_id:
                    return {
                        "tf_type": tf_type,
                        "tf_name": tf_name
                    }
        return None

class TFModifier:
    def __init__(self, tf_file_path: str):
        self.tf_file_path = tf_file_path
        if not os.path.exists(tf_file_path):
            raise FileNotFoundError(f"Terraform file not found at {tf_file_path}")

    def _find_block_end(self, content: str, start_idx: int) -> int:
        """Finds the closing brace of a resource block using brace-depth counting.
        
        Args:
            content: The full file content string.
            start_idx: Index immediately after the opening '{' of the resource block.
            
        Returns:
            Index of the matching closing '}' character.
        """
        depth = 1
        idx = start_idx
        while idx < len(content) and depth > 0:
            if content[idx] == '{':
                depth += 1
            elif content[idx] == '}':
                depth -= 1
            idx += 1
        return idx - 1  # Points at the closing '}'

    def _detect_newline(self, content: str) -> str:
        """Detects the line ending style (CRLF vs LF) used in the file."""
        if '\r\n' in content:
            return '\r\n'
        return '\n'

    def apply_remediation(self, tf_type: str, tf_name: str, remediation_type: str, new_value: str = None) -> str:
        """Modifies the target .tf file directly.
        
        Supports two remediation types:
          - 'count_zero': Injects `count = 0` into the resource block to disable it.
          - 'downsize_instance': Changes the `instance_type` attribute value.
        
        Both operations are idempotent — running them multiple times will not
        stack duplicate comments or inject redundant lines.
        
        Returns:
          "modified" if changes were successfully made and saved.
          "skipped" if the optimization is already present.
          "error" if resource not found or remediation fails.
        """
        with open(self.tf_file_path, 'r') as f:
            content = f.read()

        newline = self._detect_newline(content)

        # Regex to find the start of the resource block
        resource_pattern = rf'(resource\s+"{re.escape(tf_type)}"\s+"{re.escape(tf_name)}"\s+{{)'
        match = re.search(resource_pattern, content)
        
        if not match:
            logger.error(f"Resource {tf_type}.{tf_name} not found in {self.tf_file_path}")
            return "error"

        block_start_idx = match.end()
        block_end_idx = self._find_block_end(content, block_start_idx)
        block_content = content[block_start_idx:block_end_idx]

        if remediation_type == "count_zero":
            # Idempotency: skip if count = 0 is already present in this block
            if 'count' in block_content and '= 0' in block_content:
                logger.info(f"count = 0 already present for {tf_type}.{tf_name}. Skipping.")
                return "skipped"

            # Inject count = 0 right after the opening brace, using the file's newline style
            injection = f"{newline}  count = 0 # Added by Cloud Waste Sniper"
            modified_content = content[:block_start_idx] + injection + content[block_start_idx:]
            
        elif remediation_type == "downsize_instance":
            if not new_value:
                raise ValueError("new_value is required for downsize_instance")

            # Idempotency: check if the value is already set to the target
            already_set = re.search(rf'instance_type\s*=\s*"{re.escape(new_value)}"', block_content)
            if already_set:
                logger.info(f"instance_type already set to {new_value} for {tf_type}.{tf_name}. Skipping.")
                return "skipped"

            # Replace instance_type value (strip any previous sniper comments first)
            new_block_content = re.sub(
                r'instance_type\s*=\s*"[^"]*"(\s*#.*)?',
                f'instance_type = "{new_value}" # Downsized by Cloud Waste Sniper',
                block_content
            )
            
            modified_content = content[:block_start_idx] + new_block_content + content[block_end_idx:]
            
        else:
            logger.error(f"Unknown remediation_type: {remediation_type}")
            return "error"

        with open(self.tf_file_path, 'w') as f:
            f.write(modified_content)
            
        logger.info(f"Successfully modified {self.tf_file_path} for {tf_type}.{tf_name}")
        return "modified"

