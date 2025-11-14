   
from flexo_syside_lib.committer import commit_sysml_to_flexo


DEFAULT_PROJECT_NAME = "Flexo_SysIDE_TestProject"
sysml_sample = """
    package TestPackage {
        part Satellite {
            attribute mass = 500.0;
        }
    }
    """

FLEXO_API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJmbGV4by1tbXMtYXVkaWVuY2UiLCJpc3MiOiJodHRwOi8vZmxleG8tbW1zLXNlcnZpY2VzIiwidXNlcm5hbWUiOiJ1c2VyMDEiLCJncm91cHMiOlsic3VwZXJfYWRtaW5zIl0sImV4cCI6MTc2OTY3MzYwMH0.UqU5KOPSCbYyqbj3BBZs4u7lWbpHyDHPEd7Tbd4wWsM"

result = commit_sysml_to_flexo(
        sysml_output=sysml_sample,
        project_name=DEFAULT_PROJECT_NAME,
        verbose=True,
    )

print("Commit Result:", result)