# Portfolio Rebalancer

## Sobre este proyecto

Ante la disyuntiva de si hacer el proyecto a mano desde cero para demostrar que sé programar, me puse a pensar...

Al final del día, alguien que realmente quiere generar valor automatizando procesos sabe que para cosas chicas, **la IA es increíble para todo esto**. Además, igual después hay una instancia donde voy a tener que programar en vivo.

### El proceso

Primero (sabiendo que era un error) le di a Claude que partiera el plan para iniciar el proyecto dadas las solicitudes del enunciado.

Sabía que era un error porque primero tenía que entender la parte de negocio de lo que estoy automatizando. Pero justo me había comprado el plan pago hace 2 días y tenía ganas de usarlo 😄

Mientras Claude trabajaba, le pregunté a ChatGPT:

> *"What are all the problems at the moment of making a portfolio balancing algorithm? I know the typical that shares are not divisible, so it's never perfect"*

Para entender qué otras complejidades tiene un algoritmo de balanceo de portafolios.

### Decisiones de diseño

Claramente, vi que esto es un proyecto que puede ser **de semanas fácilmente**. No sabía si irme más por el lado matemático/algorítmico, o la parte de dejarlo más integrado/bonito. Me gustaban los dos.

Por lo que decidí acotarlo y enfocarme en:

**✅ Incluidos en el proyecto:**
- 🔹 **Indivisible assets** - Implementación con optimizador para manejar que las acciones no se pueden comprar en fracciones
- 🔹 **Capital constraints** - Rango de tolerancia del 1%-3% para permitir cierta flexibilidad en el balance

**❌ Dejados fuera del alcance:**
- ❌ Costos de transacción
- ❌ Tamaños mínimos de operación (minimum trade sizes)

Y por el lado de hacerlo interactivo
- Poder cargar los portafolios de Fintual
- Que tenaga una función para "revolver" el portafolio y poder probarlo
- Que sea una applicación tipo CLI
---

*Este README refleja el proceso real de toma de decisiones del proyecto: entender el problema, acotar el alcance, y usar las herramientas adecuadas para generar valor.*
