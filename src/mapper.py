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

    def apply_remediation(self, tf_type: str, tf_name: str, remediation_type: str, new_value: str = None) -> bool:
        """Modifies the target .tf file directly."""
        with open(self.tf_file_path, 'r') as f:
            content = f.read()

        # Regex to find the start of the resource block
        resource_pattern = rf'(resource\s+"{tf_type}"\s+"{tf_name}"\s+{{)'
        match = re.search(resource_pattern, content)
        
        if not match:
            logger.error(f"Resource {tf_type}.{tf_name} not found in {self.tf_file_path}")
            return False

        block_start_idx = match.end()
        
        if remediation_type == "count_zero":
            # Inject count = 0 right after the resource declaration
            modified_content = content[:block_start_idx] + "\n  count = 0 # Added by Cloud Waste Sniper" + content[block_start_idx:]
            
        elif remediation_type == "downsize_instance":
            if not new_value:
                raise ValueError("new_value is required for downsize_instance")
            # We need to find the instance_type attribute inside this block and replace it
            # A simple approach for MVP: extract the block and replace inside it
            # To do this safely, we should ideally count braces, but for MVP, regex is fine
            
            # Find the first closing brace after the block start
            block_end_idx = content.find('}', block_start_idx)
            block_content = content[block_start_idx:block_end_idx]
            
            # Replace instance_type
            new_block_content = re.sub(r'instance_type\s*=\s*".*"', f'instance_type = "{new_value}" # Downsized by Cloud Waste Sniper', block_content)
            
            modified_content = content[:block_start_idx] + new_block_content + content[block_end_idx:]
            
        else:
            logger.error(f"Unknown remediation_type: {remediation_type}")
            return False

        with open(self.tf_file_path, 'w') as f:
            f.write(modified_content)
            
        logger.info(f"Successfully modified {self.tf_file_path} for {tf_type}.{tf_name}")
        return True
