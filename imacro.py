# Interpreted G-Code Macros
#
# Copyright (C) 2026 Christopher Mattar (3dcoded) <info3dcoded@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import traceback
from html import escape
from pathlib import Path
from textwrap import indent

class GCodeCommandInline:
    def __init__(self, gcode):
        self._gcode = gcode
        
    def __getattr__(self, name):
        def wrapper(*args, **kwargs):
            # Convert G1('E50', F=900) -> "G1 E50 F900"
            params = " ".join(list(args) + [f"{k}{v}" for k, v in kwargs.items()])
            full_cmd = f"{name} {params}".strip()
            self._gcode.run_script_from_command(full_cmd)
            
        return wrapper

class GCodeCommandWrapper:
    def __init__(self, gcmd):
        self._gcmd = gcmd
        
    def __getattr__(self, name):
        return self._gcmd.get(name, default=None)

class PrinterWrapper:
    def __init__(self, printer):
        self._printer = printer
    
    def __getattr__(self, name):
        return PrinterObjectWrapper(self._printer.lookup_object(name, None))

class PrinterObjectWrapper:
    def __init__(self, obj):
        self._obj = obj
    
    def __getattr__(self, name):
        if isinstance(self._obj, dict):
            res = self._obj.get(name, None)
        elif hasattr(self._obj, 'get_status'):
            res = self._obj.get_status(0).get(name, None)
        return PrinterObjectWrapper(res) if isinstance(res, dict) else res
    
    def __str__(self):
        return str(self._obj if isinstance(self._obj, dict) else self._obj.get_status(0))

class iMacro:
    def __init__(self, config):
        self.config = config
        self.full_name = self.config.get_name()
        self.name = self.full_name.split()[1]
        self.printer = config.get_printer()
        
        self.script = config.get('script', None)
        
        if self.script is None:
            self.use_file = True
            self.path = self.relative_path = config.get('path')
            self.is_abs_path = config.getboolean('absolute_path', False)
            
            if not self.is_abs_path:
                printer_cfg_path = Path(self.printer.start_args['config_file'])
                config_path = printer_cfg_path.parent
                self.path = str(config_path / self.path)
        else:
            self.use_file = False
        
        self.desc = config.get('description', default='iMacro')
        
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command(
            self.name.upper(),
            self.cmd_EXECUTE,
            desc=self.desc
        )
    
    def cmd_EXECUTE(self, gcmd):
        try:
            if self.use_file:
                with open(self.path, 'r') as fp:
                    script = fp.read()
            else:
                script = self.script
            
            # Add filename for tracebacks
            compiled = compile(script, self.relative_path if self.use_file else f'iMacro {self.name}', 'exec')
            exec(
                compiled,
                {
                    'printer': PrinterWrapper(self.printer),
                    'params': GCodeCommandWrapper(gcmd),
                    'rawparams': gcmd.get_raw_command_parameters(),
                    'cmd': GCodeCommandInline(self.gcode),
                    'respond': lambda msg, unsafe=False: gcmd.respond_info(str(msg)) if unsafe else gcmd.respond_info(escape(str(msg))),
                }
            )
        except Exception as err:
            gcmd.respond_raw(indent(''.join(traceback.format_exception_only(err)), '!! '))
            if isinstance(err, IndentationError) and not self.use_file:
                gcmd.respond_info(f'<span style="color:yellow;">If you are experiencing syntax errors related to indentation, it is recommended to switch to file-based iMacros.</span>')

def load_config_prefix(config):
    return iMacro(config)