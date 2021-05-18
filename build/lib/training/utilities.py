from training.interface import Interface

if __name__ == "__main__":
    interface = Interface()
    run_again = interface.display_interface()
    while run_again:
        run_again = interface.display_interface()