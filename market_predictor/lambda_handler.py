from market_predictor.main import main


def lambda_handler(event, context):
    try:
        main()
        return {
            "statusCode": 200,
            "body": "Execution completed successfully"
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"Execution failed: {str(e)}"
        }