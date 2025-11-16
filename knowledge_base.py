"""Simple keyword-based knowledge base for local responses."""
from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any

_KB_FILE = Path(__file__).parent / "config" / "knowledge_base.json"

_DEFAULT_DATA = [
	{
		"triggers": ["quién eres", "quien eres"],
		"answer": "Soy Neno, tu asistente local. Puedo ayudarte con recordatorios, la hora y algunas tareas rápidas en tu equipo."
	},
	{
		"triggers": ["qué puedes hacer", "que puedes hacer"],
		"answer": "Puedo gestionar recordatorios, decirte la hora, abrir mi interfaz gráfica, charlar un poco y realizar algunas tareas básicas como crear documentos o buscar en la web."
	},
	{
		"triggers": ["capital de españa", "capital espan"],
		"answer": "La capital de España es Madrid."
	},
	{
		"triggers": ["celsius a fahrenheit", "°c a °f", "grados celsius a fahrenheit"],
		"answer": "Convierte °C a °F usando: (°C × 9/5) + 32. Ejemplo: 25 °C son 77 °F."
	},
	{
		"triggers": ["fahrenheit a celsius", "°f a °c"],
		"answer": "Convierte °F a °C usando: (°F − 32) × 5/9. Ejemplo: 68 °F son 20 °C."
	},
	{
		"triggers": ["kilómetros a millas", "kilometros a millas", "km a millas"],
		"answer": "1 kilómetro equivale a 0.621 millas. Multiplica los km por 0.621 para obtener millas."
	},
	{
		"triggers": ["millas a kilómetros", "millas a kilometros", "mi a km"],
		"answer": "1 milla equivale a 1.609 kilómetros. Multiplica las millas por 1.609 para obtener kilómetros."
	},
	{
		"triggers": ["kilogramos a libras", "kg a lb"],
		"answer": "1 kilogramo equivale a 2.2046 libras. Multiplica los kg por 2.2046 para obtener libras."
	},
	{
		"triggers": ["libras a kilogramos", "lb a kg"],
		"answer": "1 libra equivale a 0.4536 kg. Multiplica las libras por 0.4536 para obtener kilogramos."
	},
	{
		"triggers": ["litros a mililitros", "l a ml"],
		"answer": "1 litro equivale a 1000 mililitros. Solo multiplica los litros por 1000."
	},
	{
		"triggers": ["centímetros a pulgadas", "cm a pulgadas"],
		"answer": "1 pulgada equivale a 2.54 cm. Divide los centímetros entre 2.54 para obtener pulgadas."
	},
	{
		"triggers": ["pulgadas a centímetros", "pulg a cm"],
		"answer": "Para pasar de pulgadas a centímetros multiplica la medida en pulgadas por 2.54."
	},
	{
		"triggers": ["pies a metros", "ft a metros"],
		"answer": "1 pie equivale a 0.3048 metros. Multiplica los pies por 0.3048 para obtener metros."
	},
	{
		"triggers": ["metros a pies", "m a ft"],
		"answer": "1 metro equivale a 3.2808 pies. Multiplica los metros por 3.2808 para obtener pies."
	},
	{
		"triggers": ["comida típica española", "comida tipica espanola", "plato típico", "plato tipico", "paella"],
		"answer": "España es conocida por la paella, las tapas, la tortilla de patatas y el jamón ibérico. Cada región tiene su especialidad."
	},
	{
		"triggers": ["qué son las tapas", "que son las tapas", "qué es una tapa", "que es una tapa"],
		"answer": "Las tapas son pequeñas porciones de comida que se sirven para picar y compartir mientras se socializa, típicas en bares de toda España."
	},
	{
		"triggers": ["moneda de españa", "moneda españa", "moneda española"],
		"answer": "La moneda oficial de España es el euro (EUR) desde 2002."
	},
	{
		"triggers": ["fiestas importantes en españa", "festividades en españa", "fiestas españolas"],
		"answer": "Algunas fiestas destacadas son la Semana Santa, las Fallas de Valencia, la Feria de Abril en Sevilla y San Fermín en Pamplona."
	},
	{
		"triggers": ["equipo de fútbol más laureado", "equipo de futbol mas laureado", "mejor equipo español", "real madrid o barcelona"],
		"answer": "Históricamente, el Real Madrid es el club español con más títulos internacionales, seguido muy de cerca por el FC Barcelona."
	},
	{
		"triggers": ["dónde está la sagrada familia", "donde esta la sagrada familia", "sagrada familia ubicación"],
		"answer": "La Basílica de la Sagrada Familia está en Barcelona, en el barrio de l'Eixample. Es la obra maestra de Antoni Gaudí."
	},
	{
		"triggers": ["clima en españa", "qué tiempo hace en españa", "que tiempo hace en españa"],
		"answer": "No tengo datos en tiempo real, pero en España el clima varía: mediterráneo en la costa este, oceánico en el norte y continental en el interior."
	}
]


def _ensure_file() -> None:
	_KB_FILE.parent.mkdir(parents=True, exist_ok=True)
	if not _KB_FILE.exists():
		with open(_KB_FILE, "w", encoding="utf-8") as fh:
			json.dump(_DEFAULT_DATA, fh, indent=2, ensure_ascii=False)


def _load_entries() -> list[dict[str, Any]]:
	_ensure_file()
	try:
		with open(_KB_FILE, "r", encoding="utf-8") as fh:
			data = json.load(fh)
			if isinstance(data, list):
				return [entry for entry in data if isinstance(entry, dict)]
	except Exception as exc:
		print(f"No se pudo leer knowledge_base.json: {exc}")
	return list(_DEFAULT_DATA)


def _matches(entry: dict[str, Any], normalized_message: str) -> bool:
	triggers = entry.get("triggers")
	if isinstance(triggers, list):
		for trig in triggers:
			if isinstance(trig, str) and trig.lower() in normalized_message:
				return True
	keywords = entry.get("keywords")
	if isinstance(keywords, list) and keywords:
		if all(isinstance(keyword, str) and keyword.lower() in normalized_message for keyword in keywords):
			return True
	pattern = entry.get("pattern")
	if isinstance(pattern, str):
		try:
			if re.search(pattern, normalized_message, flags=re.IGNORECASE):
				return True
		except re.error:
			pass
	question = entry.get("question")
	if isinstance(question, str) and question.lower() == normalized_message:
		return True
	return False


def find_answer(message: str | None) -> str | None:
	if not message:
		return None
	normalized = message.strip().lower()
	if not normalized:
		return None
	for entry in _load_entries():
		if _matches(entry, normalized):
			answer = entry.get("answer")
			if isinstance(answer, str) and answer.strip():
				return answer.strip()
	return None


def knowledge_file_path() -> Path:
	"""Expose the path so users know which file to edit."""
	_ensure_file()
	return _KB_FILE
