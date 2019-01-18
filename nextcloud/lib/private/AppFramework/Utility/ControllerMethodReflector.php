<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Bernhard Posselt <dev@bernhard-posselt.com>
 * @author Morris Jobke <hey@morrisjobke.de>
 * @author Olivier Paroz <github@oparoz.com>
 * @author Robin McCorkell <robin@mccorkell.me.uk>
 * @author Thomas Müller <thomas.mueller@tmit.eu>
 *
 * @license AGPL-3.0
 *
 * This code is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License, version 3,
 * as published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License, version 3,
 * along with this program.  If not, see <http://www.gnu.org/licenses/>
 *
 */

namespace OC\AppFramework\Utility;

use \OCP\AppFramework\Utility\IControllerMethodReflector;

/**
 * Reads and parses annotations from doc comments
 */
class ControllerMethodReflector implements IControllerMethodReflector {
	public $annotations = [];
	private $types = [];
	private $parameters = [];

	/**
	 * @param object $object an object or classname
	 * @param string $method the method which we want to inspect
	 */
	public function reflect($object, $method){
		$reflection = new \ReflectionMethod($object, $method);
		$docs = $reflection->getDocComment();

		// extract everything prefixed by @ and first letter uppercase
		preg_match_all('/^\h+\*\h+@(?P<annotation>[A-Z]\w+)((?P<parameter>.*))?$/m', $docs, $matches);
		foreach($matches['annotation'] as $key => $annontation) {
			$annotationValue = $matches['parameter'][$key];
			if(isset($annotationValue[0]) && $annotationValue[0] === '(' && $annotationValue[strlen($annotationValue) - 1] === ')') {
				$cutString = substr($annotationValue, 1, -1);
				$cutString = str_replace(' ', '', $cutString);
				$splittedArray = explode(',', $cutString);
				foreach($splittedArray as $annotationValues) {
					list($key, $value) = explode('=', $annotationValues);
					$this->annotations[$annontation][$key] = $value;
				}
				continue;
			}

			$this->annotations[$annontation] = [$annotationValue];
		}

		// extract type parameter information
		preg_match_all('/@param\h+(?P<type>\w+)\h+\$(?P<var>\w+)/', $docs, $matches);
		$this->types = array_combine($matches['var'], $matches['type']);

		foreach ($reflection->getParameters() as $param) {
			// extract type information from PHP 7 scalar types and prefer them
			// over phpdoc annotations
			if (method_exists($param, 'getType')) {
				$type = $param->getType();
				if ($type !== null) {
					$this->types[$param->getName()] = (string) $type;
				}
			}

			if($param->isOptional()) {
				$default = $param->getDefaultValue();
			} else {
				$default = null;
			}
			$this->parameters[$param->name] = $default;
		}
	}

	/**
	 * Inspects the PHPDoc parameters for types
	 * @param string $parameter the parameter whose type comments should be
	 * parsed
	 * @return string|null type in the type parameters (@param int $something)
	 * would return int or null if not existing
	 */
	public function getType($parameter) {
		if(array_key_exists($parameter, $this->types)) {
			return $this->types[$parameter];
		} else {
			return null;
		}
	}

	/**
	 * @return array the arguments of the method with key => default value
	 */
	public function getParameters() {
		return $this->parameters;
	}

	/**
	 * Check if a method contains an annotation
	 * @param string $name the name of the annotation
	 * @return bool true if the annotation is found
	 */
	public function hasAnnotation($name) {
		return array_key_exists($name, $this->annotations);
	}

	/**
	 * Get optional annotation parameter by key
	 *
	 * @param string $name the name of the annotation
	 * @param string $key the string of the annotation
	 * @return string
	 */
	public function getAnnotationParameter($name, $key) {
		if(isset($this->annotations[$name][$key])) {
			return $this->annotations[$name][$key];
		}

		return '';
	}
}
