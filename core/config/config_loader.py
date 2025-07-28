#!/usr/bin/env python
# coding: utf-8
"""
Config Loader pour TECMP-Tool.

Gere le chargement de configurations predefinies, templates et profils :
- Chargement de templates de protocoles
- Profils de configuration TECMP
- Configurations d'environnement (dev, prod, test)
- Validation et application de configurations
- Support de formats multiples (JSON, YAML, INI)
"""
import logging
import os
import json
import sys
from typing import Dict, Any, List, Optional, Union, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum, auto

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    
try:
    from configparser import ConfigParser
    INI_AVAILABLE = True
except ImportError:
    INI_AVAILABLE = False


class ConfigFormat(Enum):
    """Formats de configuration supportes."""
    JSON = auto()
    YAML = auto()
    INI = auto()
    AUTO = auto()  # Detection automatique


@dataclass
class ConfigTemplate:
    """Template de configuration."""
    name: str
    description: str
    category: str
    data: Dict[str, Any]
    format_type: ConfigFormat = ConfigFormat.JSON
    version: str = "1.0"
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit le template en dictionnaire."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "tags": self.tags,
            "dependencies": self.dependencies,
            "data": self.data
        }


class ConfigLoader:
    """
    Chargeur de configurations et templates pour TECMP-Tool.
    
    Cette classe gere le chargement de differents types de configurations :
    - Templates de protocoles predefinis
    - Profils de configuration TECMP
    - Configurations d'environnement
    - Presets utilisateur personnalises
    
    Support des formats :
    - JSON (natif)
    - YAML (si disponible)
    - INI (pour les configurations simples)
    
    Fonctionnalites :
    - Detection automatique du format
    - Validation de la structure
    - Resolution des dependances
    - Fusion de configurations
    - Templates par categorie
    """
    
    def __init__(self, config_dirs: Optional[List[str]] = None):
        """
        Initialise le chargeur de configuration.
        
        Args:
            config_dirs: Repertoires de configuration (utilise les defauts si None)
        """
        self.logger = logging.getLogger("TECMP-Tool.ConfigLoader")
        
        # Repertoires de configuration
        self._config_dirs = config_dirs or self._get_default_config_dirs()
        
        # Templates charges
        self._templates: Dict[str, ConfigTemplate] = {}
        self._templates_by_category: Dict[str, List[str]] = {}
        
        # Configurations chargees
        self._configs: Dict[str, Dict[str, Any]] = {}
        
        # Metadonnees des fichiers
        self._file_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Formats supportes
        self._supported_formats = [ConfigFormat.JSON]
        if YAML_AVAILABLE:
            self._supported_formats.append(ConfigFormat.YAML)
        if INI_AVAILABLE:
            self._supported_formats.append(ConfigFormat.INI)
        
        # Initialisation
        self._ensure_config_dirs()
        self._load_builtin_templates()
        
        self.logger.info(f"ConfigLoader initialise avec {len(self._config_dirs)} repertoires")
    
    def _get_default_config_dirs(self) -> List[str]:
        """Recupere les repertoires de configuration par defaut."""
        dirs = []
        
        # Repertoire de l'application
        app_dir = Path(sys.argv[0]).parent if sys.argv else Path.cwd()
        
        # Repertoires systeme
        dirs.extend([
            str(app_dir / "config"),
            str(app_dir / "templates"),
            str(Path.home() / "Documents" / "TECMP-Tool" / "config"),
            str(Path.home() / "Documents" / "TECMP-Tool" / "templates"),
        ])
        
        # Repertoire systeme selon l'OS
        if sys.platform == "win32":
            dirs.append(str(Path.home() / "AppData" / "Local" / "TECMP-Tool" / "config"))
        else:
            dirs.append(str(Path.home() / ".config" / "tecmp-tool"))
        
        return dirs
    
    def _ensure_config_dirs(self):
        """Assure que les repertoires de configuration existent."""
        for config_dir in self._config_dirs:
            try:
                Path(config_dir).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.logger.warning(f"Impossible de creer le repertoire {config_dir}: {e}")
    
    def _load_builtin_templates(self):
        """Charge les templates integres."""
        
        # === TEMPLATES ETHERNET ===
        self.register_template(ConfigTemplate(
            name="ethernet_basic",
            description="Configuration Ethernet basique",
            category="ethernet",
            tags=["basic", "ethernet", "layer2"],
            data={
                "name": "Ethernet",
                "config": {
                    "src_mac": "00:11:22:33:44:55",
                    "dst_mac": "AA:BB:CC:DD:EE:FF",
                    "ether_type": 0x0800
                }
            }
        ))
        
        self.register_template(ConfigTemplate(
            name="ethernet_vlan",
            description="Configuration Ethernet avec VLAN",
            category="ethernet", 
            tags=["vlan", "ethernet", "layer2"],
            data={
                "name": "Ethernet",
                "config": {
                    "src_mac": "00:11:22:33:44:55",
                    "dst_mac": "AA:BB:CC:DD:EE:FF",
                    "ether_type": 0x8100,
                    "vlan_id": 100,
                    "vlan_priority": 0
                }
            }
        ))
        
        # === TEMPLATES IP ===
        self.register_template(ConfigTemplate(
            name="ipv4_basic",
            description="Configuration IPv4 basique",
            category="ip",
            tags=["ipv4", "layer3", "basic"],
            dependencies=["ethernet_basic"],
            data={
                "name": "IPv4",
                "config": {
                    "src_ip": "192.168.1.100",
                    "dst_ip": "192.168.1.200",
                    "ttl": 64,
                    "protocol": 6
                }
            }
        ))
        
        self.register_template(ConfigTemplate(
            name="ipv6_basic",
            description="Configuration IPv6 basique",
            category="ip",
            tags=["ipv6", "layer3", "basic"],
            dependencies=["ethernet_basic"],
            data={
                "name": "IPv6",
                "config": {
                    "src_ip": "2001:db8::1",
                    "dst_ip": "2001:db8::2",
                    "hop_limit": 64,
                    "next_header": 6
                }
            }
        ))
        
        # === TEMPLATES TRANSPORT ===
        self.register_template(ConfigTemplate(
            name="tcp_basic",
            description="Configuration TCP basique",
            category="transport",
            tags=["tcp", "layer4", "basic"],
            dependencies=["ipv4_basic"],
            data={
                "name": "TCP",
                "config": {
                    "src_port": 12345,
                    "dst_port": 80,
                    "flags": ["SYN"],
                    "window_size": 8192
                }
            }
        ))
        
        self.register_template(ConfigTemplate(
            name="udp_basic",
            description="Configuration UDP basique",
            category="transport",
            tags=["udp", "layer4", "basic"],
            dependencies=["ipv4_basic"],
            data={
                "name": "UDP",
                "config": {
                    "src_port": 12345,
                    "dst_port": 53
                }
            }
        ))
        
        # === TEMPLATES TECMP ===
        self.register_template(ConfigTemplate(
            name="tecmp_ethernet",
            description="TECMP pour encapsulation Ethernet",
            category="tecmp",
            tags=["tecmp", "ethernet", "encapsulation"],
            data={
                "device_id": 0x0080,
                "counter": 0,
                "version": 3,
                "message_type": 0x03,
                "data_type": 0x80,
                "device_flags": 0x000F,
                "interface_id": 0x0070128a,
                "data_flags": 0x0000
            }
        ))
        
        self.register_template(ConfigTemplate(
            name="tecmp_can",
            description="TECMP pour encapsulation CAN",
            category="tecmp",
            tags=["tecmp", "can", "automotive"],
            data={
                "device_id": 0x0080,
                "counter": 0,
                "version": 3,
                "message_type": 0x03,
                "data_type": 0x02,
                "device_flags": 0x000F,
                "interface_id": 0x0070128a,
                "data_flags": 0x0000
            }
        ))
        
        # === PROFILES COMPLETS ===
        self.register_template(ConfigTemplate(
            name="web_traffic",
            description="Trafic web HTTP/HTTPS typique",
            category="profiles",
            tags=["web", "http", "complete"],
            data={
                "stack": [
                    {
                        "name": "Ethernet",
                        "config": {
                            "src_mac": "00:11:22:33:44:55",
                            "dst_mac": "AA:BB:CC:DD:EE:FF",
                            "ether_type": 0x0800
                        }
                    },
                    {
                        "name": "IPv4",
                        "config": {
                            "src_ip": "192.168.1.100",
                            "dst_ip": "8.8.8.8",
                            "ttl": 64,
                            "protocol": 6
                        }
                    },
                    {
                        "name": "TCP",
                        "config": {
                            "src_port": 45678,
                            "dst_port": 80,
                            "flags": ["SYN"]
                        }
                    }
                ]
            }
        ))
        
        self.logger.debug(f"Charge {len(self._templates)} templates integres")
    
    def register_template(self, template: ConfigTemplate):
        """
        Enregistre un template de configuration.
        
        Args:
            template: Template a enregistrer
        """
        self._templates[template.name] = template
        
        # Organiser par categorie
        if template.category not in self._templates_by_category:
            self._templates_by_category[template.category] = []
        
        if template.name not in self._templates_by_category[template.category]:
            self._templates_by_category[template.category].append(template.name)
        
        self.logger.debug(f"Template enregistre: {template.name} ({template.category})")
    
    def get_template(self, name: str) -> Optional[ConfigTemplate]:
        """
        Recupere un template par nom.
        
        Args:
            name: Nom du template
            
        Returns:
            Template ou None si non trouve
        """
        return self._templates.get(name)
    
    def get_templates_by_category(self, category: str) -> List[ConfigTemplate]:
        """
        Recupere tous les templates d'une categorie.
        
        Args:
            category: Nom de la categorie
            
        Returns:
            Liste des templates de la categorie
        """
        template_names = self._templates_by_category.get(category, [])
        return [self._templates[name] for name in template_names if name in self._templates]
    
    def get_all_categories(self) -> List[str]:
        """
        Recupere toutes les categories disponibles.
        
        Returns:
            Liste des noms de categories
        """
        return list(self._templates_by_category.keys())
    
    def get_templates_by_tag(self, tag: str) -> List[ConfigTemplate]:
        """
        Recupere tous les templates avec un tag specifique.
        
        Args:
            tag: Tag a rechercher
            
        Returns:
            Liste des templates ayant ce tag
        """
        return [
            template for template in self._templates.values()
            if tag in template.tags
        ]
    
    def search_templates(self, query: str) -> List[ConfigTemplate]:
        """
        Recherche des templates par nom, description ou tags.
        
        Args:
            query: Terme de recherche
            
        Returns:
            Liste des templates correspondants
        """
        query_lower = query.lower()
        results = []
        
        for template in self._templates.values():
            # Rechercher dans le nom
            if query_lower in template.name.lower():
                results.append(template)
                continue
                
            # Rechercher dans la description
            if query_lower in template.description.lower():
                results.append(template)
                continue
                
            # Rechercher dans les tags
            if any(query_lower in tag.lower() for tag in template.tags):
                results.append(template)
                continue
        
        return results
    
    def load_config_file(self, file_path: str, format_type: ConfigFormat = ConfigFormat.AUTO) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Charge un fichier de configuration.
        
        Args:
            file_path: Chemin vers le fichier
            format_type: Format du fichier (AUTO pour detection automatique)
            
        Returns:
            Tuple (succes, donnees)
        """
        try:
            if not os.path.exists(file_path):
                self.logger.error(f"Fichier non trouve: {file_path}")
                return (False, None)
            
            # Detection automatique du format
            if format_type == ConfigFormat.AUTO:
                format_type = self._detect_format(file_path)
            
            # Chargement selon le format
            if format_type == ConfigFormat.JSON:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            elif format_type == ConfigFormat.YAML and YAML_AVAILABLE:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
            elif format_type == ConfigFormat.INI and INI_AVAILABLE:
                parser = ConfigParser()
                parser.read(file_path, encoding='utf-8')
                data = {section: dict(parser[section]) for section in parser.sections()}
            else:
                self.logger.error(f"Format non supporte: {format_type}")
                return (False, None)
            
            # Stocker les metadonnees
            self._file_metadata[file_path] = {
                "format": format_type,
                "size": os.path.getsize(file_path),
                "modified": os.path.getmtime(file_path)
            }
            
            self.logger.debug(f"Configuration chargee: {file_path}")
            return (True, data)
            
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement de {file_path}: {e}")
            return (False, None)
    
    def save_config_file(self, file_path: str, data: Dict[str, Any], 
                        format_type: ConfigFormat = ConfigFormat.JSON) -> bool:
        """
        Sauvegarde des donnees vers un fichier de configuration.
        
        Args:
            file_path: Chemin vers le fichier
            data: Donnees a sauvegarder
            format_type: Format du fichier
            
        Returns:
            bool: True si succes
        """
        try:
            # Creer le repertoire parent si necessaire
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Sauvegarde selon le format
            if format_type == ConfigFormat.JSON:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            elif format_type == ConfigFormat.YAML and YAML_AVAILABLE:
                with open(file_path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            elif format_type == ConfigFormat.INI and INI_AVAILABLE:
                parser = ConfigParser()
                for section, values in data.items():
                    parser[section] = values
                with open(file_path, 'w', encoding='utf-8') as f:
                    parser.write(f)
            else:
                self.logger.error(f"Format non supporte pour la sauvegarde: {format_type}")
                return False
            
            self.logger.debug(f"Configuration sauvegardee: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde de {file_path}: {e}")
            return False
    
    def load_templates_from_directory(self, directory: str, recursive: bool = True) -> int:
        """
        Charge tous les templates depuis un repertoire.
        
        Args:
            directory: Repertoire a scanner
            recursive: Scanner recursivement les sous-repertoires
            
        Returns:
            Nombre de templates charges
        """
        if not os.path.isdir(directory):
            self.logger.warning(f"Repertoire non trouve: {directory}")
            return 0
        
        loaded_count = 0
        
        # Extensions de fichiers supportees
        extensions = ['.json']
        if YAML_AVAILABLE:
            extensions.extend(['.yaml', '.yml'])
        if INI_AVAILABLE:
            extensions.extend(['.ini', '.cfg'])
        
        # Scanner le repertoire
        path_obj = Path(directory)
        pattern = "**/*" if recursive else "*"
        
        for file_path in path_obj.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                success, data = self.load_config_file(str(file_path))
                
                if success and self._is_valid_template(data):
                    try:
                        template = self._data_to_template(data, file_path.stem)
                        self.register_template(template)
                        loaded_count += 1
                    except Exception as e:
                        self.logger.warning(f"Erreur lors de la conversion du template {file_path}: {e}")
        
        self.logger.info(f"Charge {loaded_count} templates depuis {directory}")
        return loaded_count
    
    def export_template(self, template_name: str, file_path: str, 
                       format_type: ConfigFormat = ConfigFormat.JSON) -> bool:
        """
        Exporte un template vers un fichier.
        
        Args:
            template_name: Nom du template a exporter
            file_path: Chemin de destination
            format_type: Format du fichier
            
        Returns:
            bool: True si succes
        """
        template = self.get_template(template_name)
        if not template:
            self.logger.error(f"Template non trouve: {template_name}")
            return False
        
        return self.save_config_file(file_path, template.to_dict(), format_type)
    
    def create_protocol_stack(self, template_names: List[str]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Cree une pile de protocoles a partir de templates.
        
        Args:
            template_names: Liste des noms de templates
            
        Returns:
            Tuple (succes, pile de protocoles)
        """
        try:
            stack = []
            
            for template_name in template_names:
                template = self.get_template(template_name)
                if not template:
                    self.logger.error(f"Template non trouve: {template_name}")
                    return (False, [])
                
                # Ajouter le template a la pile
                if "stack" in template.data:
                    # Template contient une pile complete
                    stack.extend(template.data["stack"])
                else:
                    # Template contient un seul protocole
                    stack.append(template.data)
            
            self.logger.debug(f"Pile de protocoles creee avec {len(stack)} couches")
            return (True, stack)
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la creation de la pile: {e}")
            return (False, [])
    
    def validate_dependencies(self, template_name: str) -> Tuple[bool, List[str]]:
        """
        Valide les dependances d'un template.
        
        Args:
            template_name: Nom du template a valider
            
        Returns:
            Tuple (toutes dependances satisfaites, dependances manquantes)
        """
        template = self.get_template(template_name)
        if not template:
            return (False, [template_name])
        
        missing_deps = []
        
        for dep_name in template.dependencies:
            if dep_name not in self._templates:
                missing_deps.append(dep_name)
        
        return (len(missing_deps) == 0, missing_deps)
    
    def resolve_dependencies(self, template_names: List[str]) -> Tuple[bool, List[str]]:
        """
        Resout automatiquement les dependances d'une liste de templates.
        
        Args:
            template_names: Liste des templates de base
            
        Returns:
            Tuple (succes, liste complete avec dependances)
        """
        try:
            resolved = []
            processed = set()
            
            def _resolve_recursive(name: str):
                if name in processed:
                    return
                
                template = self.get_template(name)
                if not template:
                    raise ValueError(f"Template non trouve: {name}")
                
                # Resoudre les dependances d'abord
                for dep_name in template.dependencies:
                    _resolve_recursive(dep_name)
                
                # Ajouter le template courant
                if name not in processed:
                    resolved.append(name)
                    processed.add(name)
            
            # Resoudre toutes les dependances
            for template_name in template_names:
                _resolve_recursive(template_name)
            
            self.logger.debug(f"Dependances resolues: {resolved}")
            return (True, resolved)
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la resolution des dependances: {e}")
            return (False, template_names)
    
    def get_template_info(self, template_name: str) -> Optional[Dict[str, Any]]:
        """
        Recupere les informations completes d'un template.
        
        Args:
            template_name: Nom du template
            
        Returns:
            Dictionnaire d'informations ou None
        """
        template = self.get_template(template_name)
        if not template:
            return None
        
        # Valider les dependances
        deps_valid, missing_deps = self.validate_dependencies(template_name)
        
        return {
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "version": template.version,
            "tags": template.tags,
            "dependencies": template.dependencies,
            "dependencies_valid": deps_valid,
            "missing_dependencies": missing_deps,
            "data_size": len(str(template.data))
        }
    
    def _detect_format(self, file_path: str) -> ConfigFormat:
        """Detecte le format d'un fichier de configuration."""
        ext = Path(file_path).suffix.lower()
        
        if ext == '.json':
            return ConfigFormat.JSON
        elif ext in ['.yaml', '.yml'] and YAML_AVAILABLE:
            return ConfigFormat.YAML
        elif ext in ['.ini', '.cfg'] and INI_AVAILABLE:
            return ConfigFormat.INI
        else:
            # Defaut : JSON
            return ConfigFormat.JSON
    
    def _is_valid_template(self, data: Dict[str, Any]) -> bool:
        """Verifie si des donnees sont un template valide."""
        required_fields = ["name", "description", "category"]
        return all(field in data for field in required_fields)
    
    def _data_to_template(self, data: Dict[str, Any], default_name: str) -> ConfigTemplate:
        """Convertit des donnees en template."""
        return ConfigTemplate(
            name=data.get("name", default_name),
            description=data.get("description", ""),
            category=data.get("category", "custom"),
            version=data.get("version", "1.0"),
            tags=data.get("tags", []),
            dependencies=data.get("dependencies", []),
            data=data.get("data", data)
        )