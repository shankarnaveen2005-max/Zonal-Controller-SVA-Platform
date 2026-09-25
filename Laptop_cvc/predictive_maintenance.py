"""
Machine-Learning Predictive Maintenance Module
for the Zonal Controller-Based SVA Platform.

Inputs:
    Voltage
    Current
    Temperature
    Vibration
    RPM
    Communication Health

Outputs:
    NORMAL
    WARNING
    CRITICAL

The current prototype trains on synthetic vehicle operating data.
Later, the same prediction interface can use real STM32 sensor data.
"""

from dataclasses import dataclass
import random

import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split


# ============================================================
# RANDOM SEED
# ============================================================

RANDOM_SEED = 42

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


# ============================================================
# CONDITION DATA
# ============================================================

@dataclass
class ConditionData:
    voltage: float
    current: float
    temperature: float
    vibration: float
    rpm: float
    communication_health: float


# ============================================================
# PREDICTION RESULT
# ============================================================

@dataclass
class MaintenanceResult:
    condition: str
    confidence: float
    risk_score: float
    recommendation: str


def apply_v2x_context(
    result: MaintenanceResult,
    alerts: list[object],
) -> MaintenanceResult:
    """Add external safety-alert context without changing the ML prediction."""
    if not alerts:
        return result

    critical = any(
        getattr(alert, "payload", {}).get("severity") == "CRITICAL"
        for alert in alerts
    )
    adjustment = 20.0 if critical else 10.0
    return MaintenanceResult(
        condition="CRITICAL" if critical else result.condition,
        confidence=result.confidence,
        risk_score=min(100.0, result.risk_score + adjustment),
        recommendation=(
            "V2X safety alert active. Review external hazard before continuing. "
            + result.recommendation
        ),
    )


# ============================================================
# SYNTHETIC TRAINING DATA GENERATOR
# ============================================================

class TrainingDataGenerator:

    def __init__(
        self,
        samples_per_class: int = 500,
    ) -> None:

        self.samples_per_class = samples_per_class


    def _normal_sample(self) -> list[float]:

        return [
            random.uniform(12.0, 14.5),     # Voltage
            random.uniform(2.0, 7.0),       # Current
            random.uniform(30.0, 65.0),     # Temperature
            random.uniform(0.5, 3.5),       # Vibration
            random.uniform(800, 3500),      # RPM
            random.uniform(90, 100),        # Communication health
        ]


    def _warning_sample(self) -> list[float]:

        return [
            random.uniform(11.2, 14.9),
            random.uniform(6.5, 11.0),
            random.uniform(60.0, 85.0),
            random.uniform(3.0, 6.0),
            random.uniform(3000, 5000),
            random.uniform(65, 92),
        ]


    def _critical_sample(self) -> list[float]:

        return [
            random.uniform(9.5, 12.0),
            random.uniform(10.0, 16.0),
            random.uniform(80.0, 110.0),
            random.uniform(5.5, 10.0),
            random.uniform(4500, 6500),
            random.uniform(20, 70),
        ]


    def generate(
        self,
    ) -> tuple[np.ndarray, np.ndarray]:

        features = []
        labels = []

        for _ in range(self.samples_per_class):

            features.append(
                self._normal_sample()
            )

            labels.append(
                "NORMAL"
            )

        for _ in range(self.samples_per_class):

            features.append(
                self._warning_sample()
            )

            labels.append(
                "WARNING"
            )

        for _ in range(self.samples_per_class):

            features.append(
                self._critical_sample()
            )

            labels.append(
                "CRITICAL"
            )

        return (
            np.array(features, dtype=float),
            np.array(labels),
        )


# ============================================================
# ML PREDICTIVE MAINTENANCE ENGINE
# ============================================================

class PredictiveMaintenance:

    def __init__(self) -> None:

        self.model = RandomForestClassifier(
            n_estimators=150,
            max_depth=10,
            random_state=RANDOM_SEED,
        )

        self.trained = False
        self.accuracy = 0.0


    # ========================================================
    # TRAIN MODEL
    # ========================================================

    def train(
        self,
        samples_per_class: int = 500,
    ) -> float:

        generator = TrainingDataGenerator(
            samples_per_class
        )

        features, labels = generator.generate()

        (
            x_train,
            x_test,
            y_train,
            y_test,
        ) = train_test_split(
            features,
            labels,
            test_size=0.20,
            random_state=RANDOM_SEED,
            stratify=labels,
        )

        self.model.fit(
            x_train,
            y_train,
        )

        predictions = self.model.predict(
            x_test
        )

        self.accuracy = accuracy_score(
            y_test,
            predictions,
        )

        self.trained = True

        return self.accuracy


    # ========================================================
    # CALCULATE FAILURE RISK
    # ========================================================

    def _calculate_risk(
        self,
        probabilities: dict[str, float],
    ) -> float:

        normal_probability = probabilities.get(
            "NORMAL",
            0.0,
        )

        warning_probability = probabilities.get(
            "WARNING",
            0.0,
        )

        critical_probability = probabilities.get(
            "CRITICAL",
            0.0,
        )

        risk = (
            warning_probability * 50.0
            + critical_probability * 100.0
        )

        # Small adjustment based on loss of normal probability.
        risk = max(
            risk,
            (1.0 - normal_probability) * 50.0,
        )

        return min(
            risk,
            100.0,
        )


    # ========================================================
    # MAINTENANCE RECOMMENDATION
    # ========================================================

    @staticmethod
    def _recommendation(
        condition: str,
    ) -> str:

        if condition == "NORMAL":

            return (
                "Vehicle operating normally. "
                "Continue regular monitoring."
            )

        if condition == "WARNING":

            return (
                "Possible component degradation detected. "
                "Preventive inspection is recommended."
            )

        return (
            "High failure risk detected. "
            "Immediate diagnostics and maintenance are recommended."
        )


    # ========================================================
    # PREDICT CONDITION
    # ========================================================

    def predict(
        self,
        data: ConditionData,
    ) -> MaintenanceResult:

        if not self.trained:

            self.train()

        features = np.array(
            [[
                data.voltage,
                data.current,
                data.temperature,
                data.vibration,
                data.rpm,
                data.communication_health,
            ]],
            dtype=float,
        )

        predicted_condition = (
            self.model.predict(
                features
            )[0]
        )

        probability_values = (
            self.model.predict_proba(
                features
            )[0]
        )

        probabilities = {
            class_name: probability
            for class_name, probability
            in zip(
                self.model.classes_,
                probability_values,
            )
        }

        confidence = probabilities.get(
            predicted_condition,
            0.0,
        ) * 100.0

        risk_score = self._calculate_risk(
            probabilities
        )

        recommendation = self._recommendation(
            predicted_condition
        )

        return MaintenanceResult(
            condition=predicted_condition,
            confidence=confidence,
            risk_score=risk_score,
            recommendation=recommendation,
        )


# ============================================================
# DISPLAY TEST RESULT
# ============================================================

def display_result(
    name: str,
    data: ConditionData,
    result: MaintenanceResult,
) -> None:

    print(
        f"\n{name}"
    )

    print(
        "----------------------------------------------"
    )

    print(
        f"Voltage              : {data.voltage:.2f} V"
    )

    print(
        f"Current              : {data.current:.2f} A"
    )

    print(
        f"Temperature          : {data.temperature:.2f} °C"
    )

    print(
        f"Vibration            : {data.vibration:.2f}"
    )

    print(
        f"RPM                  : {data.rpm:.0f}"
    )

    print(
        f"Communication Health : "
        f"{data.communication_health:.1f}%"
    )

    print()

    print(
        f"ML Prediction        : {result.condition}"
    )

    print(
        f"Prediction Confidence: {result.confidence:.1f}%"
    )

    print(
        f"Failure Risk         : {result.risk_score:.1f}%"
    )

    print(
        f"Recommendation       : {result.recommendation}"
    )


# ============================================================
# DEMONSTRATION
# ============================================================

def run_demo() -> None:

    print(
        "\n=============================================="
    )

    print(
        "     SVA ML PREDICTIVE MAINTENANCE"
    )

    print(
        "=============================================="
    )


    # ========================================================
    # CREATE MODEL
    # ========================================================

    predictive_system = PredictiveMaintenance()


    # ========================================================
    # TRAIN MODEL
    # ========================================================

    print(
        "\nGenerating simulated operating dataset..."
    )

    print(
        "Training Random Forest model..."
    )

    accuracy = predictive_system.train(
        samples_per_class=500
    )

    print(
        f"\nModel test accuracy: "
        f"{accuracy * 100:.2f}%"
    )


    # ========================================================
    # NORMAL TEST
    # ========================================================

    normal_data = ConditionData(
        voltage=13.1,
        current=4.5,
        temperature=45.0,
        vibration=1.8,
        rpm=2200,
        communication_health=98,
    )


    # ========================================================
    # WARNING TEST
    # ========================================================

    warning_data = ConditionData(
        voltage=11.8,
        current=9.0,
        temperature=74.0,
        vibration=4.5,
        rpm=4100,
        communication_health=78,
    )


    # ========================================================
    # CRITICAL TEST
    # ========================================================

    critical_data = ConditionData(
        voltage=10.5,
        current=14.0,
        temperature=98.0,
        vibration=8.0,
        rpm=5900,
        communication_health=40,
    )


    # ========================================================
    # RUN TESTS
    # ========================================================

    tests = {
        "NORMAL OPERATING CONDITION": normal_data,
        "WARNING OPERATING CONDITION": warning_data,
        "CRITICAL OPERATING CONDITION": critical_data,
    }

    for name, data in tests.items():

        result = predictive_system.predict(
            data
        )

        display_result(
            name,
            data,
            result,
        )


    # ========================================================
    # COMPLETION
    # ========================================================

    print(
        "\n=============================================="
    )

    print(
        "ML Predictive Maintenance Test Completed"
    )

    print(
        "==============================================\n"
    )


# ============================================================
# START PROGRAM
# ============================================================

if __name__ == "__main__":

    try:

        run_demo()

    except KeyboardInterrupt:

        print(
            "\nPredictive maintenance test stopped by user."
        )