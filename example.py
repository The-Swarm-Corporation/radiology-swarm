from radiology_swarm.main import run_diagnosis_agents

print(run_diagnosis_agents(
    "Analyze this image and provide both an analysis and a treatment plan",
    img="xray.jpeg",
    output_file_name="first_xray_analysis.md"
))