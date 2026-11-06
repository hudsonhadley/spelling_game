## Running
1. From the root, run ```python -m venv .venv``` to create a virtual environment
2. Start the virtual environment using:
  * If linux, ```source .venv/bin/activate``` 
  * If powershell, ```.\.venv\scripts\Activate.ps1```

3. Copy ```.appenv.example``` and rename to ```.appenv```. Set ```MW_API_KEY```.

3. Create the module using ```python -m pip install -e .``` from the root
4. Run the application using ```python -m flask --app spelling_game.wsgi run``` from the root directory