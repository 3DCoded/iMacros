# Intelligent G-Code Macros
#
# Copyright (C) 2026 Christopher Mattar (3dcoded) <info3dcoded@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

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
        return self._gcmd.get(name)

class PrinterIntelliMacro:
    def __init__(self, config):
        self.config = config
        self.full_name = self.config.get_name()
        self.name = self.full_name.split()[1]
        self.printer = config.get_printer()
        
        self.script = config.get('script')
        self.desc = config.get('description', default='Intelli-G-Code Macro')
        
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command(
            self.name.upper(),
            self.cmd_EXECUTE,
            desc=self.desc
        )
    
    def cmd_EXECUTE(self, gcmd):
        try:
            exec(
                self.script,
                {
                    'printer': self.printer,
                    'params': GCodeCommandWrapper(gcmd),
                    'cmd': GCodeCommandInline(self.gcode),
                    'respond': lambda msg: gcmd.respond_info(str(msg))
                }
            )
        except Exception as err:
            gcmd.respond_raw(f'!! {err}')

def load_config_prefix(config):
    return PrinterIntelliMacro(config)