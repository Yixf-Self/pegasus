#ifndef MPICOMM_H
#define MPICOMM_H

#include "comm.h"

class MPICommunicator : public Communicator {
private:
    unsigned long bytes_sent;
    unsigned long bytes_recvd;
    
public:
    MPICommunicator(int *argc, char ***argv);
    virtual ~MPICommunicator();
    virtual void send_message(Message *message, int dest);
    virtual Message *recv_message();
    virtual bool message_waiting();
    virtual void barrier();
    virtual void abort(int exitcode);
    virtual int rank();
    virtual int size();
    virtual unsigned long sent();
    virtual unsigned long recvd();
    int wait_for_message();
};

#endif /* MPICOMM_H */

