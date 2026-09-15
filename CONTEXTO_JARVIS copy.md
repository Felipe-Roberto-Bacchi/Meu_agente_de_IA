PS C:\projeto ia\teste 2\Meu-agente-IA-main> & C:\Users\felip\AppData\Local\Programs\Python\Python311\python.exe "c:/projeto ia/teste 2/Meu-agente-IA-main/simulador_interface.py"

==================================================
   JARVIS - SIMULADOR DE INTERFACE NEON
==================================================

[1/4] Iniciando servidor de interface...
[2/4] Abrindo painel visual...
[3/4] Inicializando rosquinhas neons...
[ERRO] Não foi possível conectar ao servidor. Verifique a porta 8000.
PS C:\projeto ia\teste 2\Meu-agente-IA-main> & C:\Users\felip\AppData\Local\Programs\Python\Python311\python.exe "c:/projeto ia/teste 2/Meu-agente-IA-main/MODULOS/system/interface_server.py"
pygame 2.6.1 (SDL 2.28.4, Python 3.11.9)
Hello from the pygame community. https://www.pygame.org/contribute.html
C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\torch\cuda\__init__.py:58: FutureWarning: The pynvml package is deprecated. Please install nvidia-ml-py instead. If you did not install pynvml directly, please report this to the maintainers of the package that installed pynvml for you.
  import pynvml  # type: ignore[import]
WARNING: All log messages before absl::InitializeLog() is called are written to STDERR
I0000 00:00:1789513286.280297   12060 port.cc:153] oneDNN custom operations are on. You may see slightly different numerical results due to floating-point round-off errors from different computation orders. To turn them off, set the environment variable `TF_ENABLE_ONEDNN_OPTS=0`.
WARNING: All log messages before absl::InitializeLog() is called are written to STDERR
I0000 00:00:1789513299.012685   12060 port.cc:153] oneDNN custom operations are on. You may see slightly different numerical results due to floating-point round-off errors from different computation orders. To turn them off, set the environment variable `TF_ENABLE_ONEDNN_OPTS=0`.

============================================================
ERRO FATAL NO MODULO INTERFACE_SERVER
============================================================
Traceback (most recent call last):
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\transformers\activations_tf.py", line 22, in <module>
    import tf_keras as keras
ModuleNotFoundError: No module named 'tf_keras'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "c:\projeto ia\teste 2\Meu-agente-IA-main\MODULOS\system\interface_server.py", line 21, in <module>
    from MODULOS.brain.selector import selector as brain_selector
  File "c:\projeto ia\teste 2\Meu-agente-IA-main\MODULOS\brain\__init__.py", line 10, in <module>
    from MODULOS.brain.memory.handler import _processar_memoria
  File "c:\projeto ia\teste 2\Meu-agente-IA-main\MODULOS\brain\memory\handler.py", line 4, in <module>
    from MODULOS.memory import memory_long
  File "c:\projeto ia\teste 2\Meu-agente-IA-main\MODULOS\memory\memory_long.py", line 24, in <module>
    _EMB = embedding_functions.SentenceTransformerEmbeddingFunction(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\chromadb\utils\embedding_functions\sentence_transformer_embedding_function.py", line 29, in __init__
    from sentence_transformers import SentenceTransformer
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\sentence_transformers\__init__.py", line 15, in <module>
    from sentence_transformers.cross_encoder import (
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\sentence_transformers\cross_encoder\__init__.py", line 3, in <module>
    from .CrossEncoder import CrossEncoder
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\sentence_transformers\cross_encoder\CrossEncoder.py", line 35, in <module>
    from sentence_transformers.cross_encoder.fit_mixin import FitMixin
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\sentence_transformers\cross_encoder\fit_mixin.py", line 20, in <module>
    from sentence_transformers.datasets.NoDuplicatesDataLoader import NoDuplicatesDataLoader
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\sentence_transformers\datasets\__init__.py", line 13, in <module>
    from .ParallelSentencesDataset import ParallelSentencesDataset
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\sentence_transformers\datasets\ParallelSentencesDataset.py", line 19, in <module>
    from sentence_transformers import SentenceTransformer
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\sentence_transformers\SentenceTransformer.py", line 36, in <module>
    from sentence_transformers.model_card import SentenceTransformerModelCardData, generate_model_card
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\sentence_transformers\model_card.py", line 26, in <module>
    from transformers.integrations import CodeCarbonCallback
  File "<frozen importlib._bootstrap>", line 1229, in _handle_fromlist
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\transformers\utils\import_utils.py", line 2317, in __getattr__
    module = self._get_module(self._class_to_module[name])
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\transformers\utils\import_utils.py", line 2347, in _get_module
    raise e
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\transformers\utils\import_utils.py", line 2345, in _get_module
    return importlib.import_module("." + module_name, self.__name__)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\importlib\__init__.py", line 126, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\transformers\integrations\integration_utils.py", line 60, in <module>
    from .. import TFPreTrainedModel
  File "<frozen importlib._bootstrap>", line 1229, in _handle_fromlist
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\transformers\utils\import_utils.py", line 2317, in __getattr__
    module = self._get_module(self._class_to_module[name])
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\transformers\utils\import_utils.py", line 2347, in _get_module
    raise e
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\transformers\utils\import_utils.py", line 2345, in _get_module
    return importlib.import_module("." + module_name, self.__name__)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\importlib\__init__.py", line 126, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\transformers\modeling_tf_utils.py", line 38, in <module>
    from .activations_tf import get_tf_activation
  File "C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages\transformers\activations_tf.py", line 27, in <module>
    raise ValueError(
ValueError: Your currently installed version of Keras is Keras 3, but this is not yet supported in Transformers. Please install the backwards-compatible tf-keras package with `pip install tf-keras`.
============================================================

Janela travada para diagnóstico. Pressione ENTER para fechar...