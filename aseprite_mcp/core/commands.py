import subprocess
import tempfile
import os
import dotenv

_ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
dotenv.load_dotenv(dotenv_path=_ENV_PATH)

class AsepriteCommand:
    """Helper class for running Aseprite commands."""
    
    @staticmethod
    def run_command(args):
        """Run an Aseprite command with proper error handling.
        
        Args:
            args: List of command arguments
            
        Returns:
            tuple: (success, output) where success is a boolean and output is the command output
        """
        try:
            dotenv.load_dotenv(dotenv_path=_ENV_PATH)
            cmd = [os.getenv('ASEPRITE_PATH', 'aseprite')] + args
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stderr
    
    @staticmethod
    def execute_lua_script(script_content, filename=None):
        """Execute a Lua script in Aseprite.
        
        Args:
            script_content: Lua script code to execute
            filename: Optional filename to open before executing script
            
        Returns:
            tuple: (success, output)
        """
        # Create a temporary file for the script
        with tempfile.NamedTemporaryFile(suffix='.lua', delete=False, mode='w') as tmp:
            tmp.write(script_content)
            script_path = tmp.name
        
        try:
            args = ["--batch"]
            if filename and os.path.exists(filename):
                args.append(filename)
            args.extend(["--script", script_path])
            
            success, output = AsepriteCommand.run_command(args)
            return success, output
        finally:
            # Clean up the temporary script file
            os.remove(script_path)
