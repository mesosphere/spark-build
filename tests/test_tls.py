import logging
import pytest

import spark_utils as utils

log = logging.getLogger(__name__)

@pytest.fixture(scope="module", autouse=True)
def setup_spark(configure_security_spark, configure_universe):
    service_options = {
        "service": {
            "tls": {
                "enabled": True,
                "protocol": "TLSv1.2",
                "keystore": "MIIKLwIBAzCCCegGCSqGSIb3DQEHAaCCCdkEggnVMIIJ0TCCBXUGCSqGSIb3DQEHAaCCBWYEggViMIIFXjCCBVoGCyqGSIb3DQEMCgECoIIE+zCCBPcwKQYKKoZIhvcNAQwBAzAbBBQ7cf3ZKflHCIQCcwSczlU0J7eJcwIDAMNQBIIEyMhBBvjfGOfbzHas4pw3luSDxntNS4IQwHwXr95QPYrGuEgbO5qR6Ssup4zZMjUgqVL0Z+pKArI47yZPhynmjynXaYTlJ2qG6mI2al3JaaTODa7A/ilv/Lso6A31uMYyXy8/BDC5/5ASF5YVKc6CGpTmKCyaUNUV6PYA/wRwZ9Zt4ksCWDtrO5o5Z5VtHerrD7+gZ2Wj3pfvYxOBeU1B2LNZcywcZLcsLA9mA6BE1go9V67CaH9xgukOLTfqWgRmTn2DJnHAJsqRjue59lFQNweo4Ricwj5NyHH74bFNbURY2Ttq509bEEfPTqP9g+2UeA0QyegEnRVgQCCmazAzk2/PcUR9+2vDohGi9i69jBJUeIOCmptzGXYmTD/hlIRfZmRPkWQsApIih2vAErM89IXFiIbH9QRqZB38Cv8eOq1NvY6pt03Zd2tN/85q57wq3ob7pB8agbYjhUJ7wlcfVaMvw4GIZevUsTJGIa4MoJSOWznrd29jgIy5LEghY2+JBBehNaex2tJ+VwbYAFSrlbvGG40vqx/1ibHnh2Jewfl1rh77Fq6Tz1InXcn19f2RSNWQXtKYrrVNat81xiBzYNMMsi50CAAF/J0aEqcwT1SUWl0QNZCTaz6fCHnasoI0ih7sbsdjkmoyt7d25/NWCbMIVRWHBHNv9Ehtd6h7KCDMfkHV8KEMFxl23ErzNavQkklf1JSACve+GCMXwfQzmyKeiWWPtwFmN/1NxGjrFDX2bZxE6ClH9ZGSIs8RwPPyA2eCTHiDaXQdxIdq0XWlVUV6MoFAyl6GHTbTuyWlQWfHUMTMQup89tyRCPhfXkf3kdJ8gFbjsRms4Fz7ZC7oKz//DTYAKNmqPD88VJKPOC+7wKR2uHwLPUsaUA8QWq+ypFOpyEgANiWT3iJ/nUxQkNIg57RkdN58/BAvgpuc7CWuM7Pu2RAOQzZEn4eD7tHQpJMPAgdgiltu+V0VFVJmKKslBNRl2cajNyc0wLNGQAN3Xy2rUjlWx71dYfpmDb8n0sI3RWwijZtRlO0ON5U8uEGk5f28i7RS1o3kgYVSZ1tgUqoMw556LpDogQh8LLS1ALBm8rpDyaarsVq6jvi7wXwWmr+YQA7qgc5dBu6xDGEijliIyX0eZ/TPHK0w5ZW1cPyXk/Ch9tHxHHgXiO1vFHol0sCYHNj6dchezicEp4XnJVJsPznHZEsIqlAKmvUEU3bR2KqS8XW4gqzahifG/cE5sRee6+1yPnhwbkVVgryfrp7YN4EJw4jBZHHwC2ZdUO9LtJKppDt4sLH3IcQ8FYebKVPIJk7e8B3CXf3mUxve6XuAtljd8ljsCuWdp11H2VEVrCs4J6RSi0yEZnKNQVTlYFb+TZKly/Rw2FuDxJ2/mgBcPiDYIVAURPsqw1VLHhlsz5099/pf6MkfifeIo41N/NfVldkgJjEsMNNLCtbtUR7TnB4iDXoy8RfHeFwCmtF700FVRPugMGBGjWtEzwtTlWDg07+dQaxVuP8Vkopc6blgeDNjKjH0PVny1Wdo0MhrkuJFu+diCT3hHRfyfr2Ks0K3NQZ4fqDOtraDrmaipgd1Ak6t60efoY5BpktkFGOU6f9q6Ueqqp2dY8z5AAtg3gFkkfRt9TFMMCcGCSqGSIb3DQEJFDEaHhgAcwBlAHIAdgBlAHIALQBhAGwAaQBhAHMwIQYJKoZIhvcNAQkVMRQEElRpbWUgMTU1OTIwOTY0NjAwODCCBFQGCSqGSIb3DQEHBqCCBEUwggRBAgEAMIIEOgYJKoZIhvcNAQcBMCkGCiqGSIb3DQEMAQYwGwQUdYG1qFthsSXJgI1l+P8leohZ9y0CAwDDUICCBABkOcc0175UDy+ZUnOfyjfVVFSl2Rl3t8032P0uXP2XRzhM5IuM4obON5YCAI6kztFgy0w7qI0VdyI9LBT9Zwe4vvwBCS4IBob2M7F4g84xT2MBzoMmijbuIwJVlfaUb82y+z7uuZ81ZmImkRaC5uCYeHM9ab4w3alrgamWVjcYWk/ykFB7RRnvRh7blEorDK58P5AX7rMJ6jp8RrL9HhhbL+1sbztjjdPLRfsbIQqv/rhKAM5htzhybml8rP6ohusVVtLdbK+A88YGUCIX1Y0O518MOvCABaO87SWe/EZthC18bGsSai8mPsol3E3ersGikG2QECtLZfbIt32Nflp9SFBMf03sk//EimK9pIkBTwiYf8JzhNxxruo81HAo+MTjoFT3ZLEhl0sbZ57qn9npTnhtYxG5MGK0w6liF1egWq4gAoVQs//FePCbj0JJif4+irBi36Ju7GbW7cqCYmwYx/iiyQ7sB9f2qK3zuD8R1DfZi+gpnf4WJ56Sy/MsCUiyVYiSNvnp8lKA8GfhEXZawDIy2ymLv75fvUGlt36mI7LqlGOR7meZYrSem0LtY0Ivjd4ZSt4IiA99BlNUzeSQXOJhlwvt62WHpA1PGzRhliaz7m1ijcM/FmWgT3DtWsNXgv8FY0LHxnh8lUMuInFnYiGpv2CLuavl1QxWHKqBohtt9BDeIBsMpgsxnQyfbDPJ7N50Am/ipB9kWmXIN2htMlgcfEQF7kaSVacZQb9kbbNyxdgYfk/oD8a1BP4fdtFQN5j3GPMViyg8T37OD6uet5io72Oisd8K3YrTLaHmxfzBaDFhOZuKn0zNJoiynK1mze9mgni6Gr/0ja3E1uwi4usZTHGztG+gtrZe7YHmYPFWU4K33a8Cv2dF+XJxDi33JJEGVlcm9ZGv80mvMM/AMUbpWiLyOyXSUyMIt5hs8E9/RtOcHRPz+o7w/1reZBrX2LNOLTajg/v2uA7XwePjuw4qOEZk55aDVE+oBsaGaAoyO2MXnbfbvs6ll5qDjHHxqvajjV+nckCYQescRJc8xLvqBHUY3tgllplDDG8ci+T5GoR/GChnhO6Kn312fnlWbmV6NgLp55RWFaxfJ0YYc9Ex8G08jMEQA+Vb3Y99wmimkzk1a4HLipRcOAlKOMfidvMbNL/9VxqC+fPdLeW+F9XWOz1AK8AfSJbiwZLZhOAp6yqberv7+4NshMugdRdUC0ZkyvCnEfgTtxE1e9c9BALGVrGwsU2l+YGVYqolXIAgTpzW5Zdo61+5fC0ywWLvYeV4go6kojakEGEi5XUCWqoOKtutiPINZ54tSWb213dfaMZBV+U9CGHIDMKBT8oK36R26q7NzZylig0eAOtKMD4wITAJBgUrDgMCGgUABBTukFLt71PwtPeKzC1lXXejX5Hl0AQUosMoZ1fvQ9IioyphvRc+YSPYMP8CAwGGoA==",
                "keypassword": "deleteme",
                "keystore_password": "deleteme"
            }
        }
    }
    try:
        utils.upload_dcos_test_jar()
        utils.require_spark(additional_options=service_options)
        yield
    finally:
        utils.teardown_spark()


@pytest.mark.sanity
def test_driver_over_tls():
    utils.run_tests(
        app_url=utils.SPARK_EXAMPLES,
        app_args="100",
        expected_output="Pi is roughly 3",
        args=["--class org.apache.spark.examples.SparkPi"])
