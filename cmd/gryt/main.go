package main

import (
	"fmt"
	"os"
	"os/exec"
)

func usage() {
	fmt.Println("gryt CLI (Go): usage\n  gryt init [path]\n  gryt run <script.py> [--parallel]\n  gryt validate <script.py>")
}

func forwardToPython(args []string) int {
	cmd := exec.Command("python", append([]string{"-m", "gryt.cli"}, args...)...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin
	if err := cmd.Run(); err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			return exitErr.ExitCode()
		}
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return 1
	}
	return 0
}

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(1)
	}
	cmd := os.Args[1]
	switch cmd {
	case "init", "run", "validate":
		os.Exit(forwardToPython(os.Args[1:]))
	case "help", "-h", "--help":
		usage()
		os.Exit(0)
	default:
		fmt.Fprintf(os.Stderr, "unknown command: %s\n", cmd)
		usage()
		os.Exit(1)
	}
}
