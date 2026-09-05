import pandas as pd

from ml.predict import predict_recovery


df = pd.read_csv("data/payments_training.csv")

payment = df.iloc[0].to_dict()

probability = predict_recovery(payment)

print("=" * 60)
print("RecoveryOS ML Prediction Test")
print("=" * 60)

print("\nPayment:")
print(f"Payment ID: {payment['payment_id']}")
print(f"Amount: ₹{payment['amount']}")
print(f"Method: {payment['payment_method']}")
print(f"Failure: {payment['failure_code']}")

print("\nActual outcome:")
print(f"Recovered: {payment['recovered']}")

print("\nML prediction:")
print(f"Recovery probability: {probability:.2%}")